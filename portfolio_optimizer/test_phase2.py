"""
Test script for Phase 2: Optimizer and Risk Calculator
Run this to verify all optimization methods and risk calculations work
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import Phase 2 modules
from backend.services import (
    EnhancedPortfolioOptimizer,
    RiskMetricsCalculator,
    PortfolioDataService
)
from backend.services.optimizer import create_optimizer
from backend.services.risk_calculator import create_risk_calculator

# Import Phase 1 modules for data access
from backend.database import (
    search_assets,
    validate_symbols_exist
)

def print_separator(title=""):
    """Print a nice separator"""
    if title:
        print(f"\n{'='*70}")
        print(f"  {title}")
        print(f"{'='*70}\n")
    else:
        print(f"{'='*70}\n")


def find_valid_test_symbols():
    """Find valid symbols for testing"""
    # Try common US stocks
    test_candidates = [
        "AAPL.US", "MSFT.US", "GOOGL.US", "AMZN.US", "SPY.US",
        "AAPL", "MSFT", "GOOGL", "AMZN", "SPY"
    ]
    
    validation = validate_symbols_exist(test_candidates)
    valid = [s for s, exists in validation.items() if exists]
    
    if len(valid) >= 3:
        return valid[:3]
    
    # Fallback: search for common symbols
    for query in ['AAPL', 'SPY', 'MSFT']:
        results = search_assets(query, limit=3)
        for asset in results:
            if asset.symbol not in valid:
                valid.append(asset.symbol)
                if len(valid) >= 3:
                    return valid
    
    return valid


def test_data_service():
    """Test PortfolioDataService"""
    print_separator("TEST 1: Portfolio Data Service")
    
    # Find valid symbols
    symbols = find_valid_test_symbols()
    
    if len(symbols) < 2:
        print("❌ Not enough valid symbols found for testing")
        return False, []
    
    print(f"Using symbols: {', '.join(symbols)}")
    
    # Create data service
    service = PortfolioDataService()
    
    # Get date range (1 year)
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=365)
    
    print(f"\nFetching data from {start_date} to {end_date}...")
    
    # Prepare optimization data
    data = service.prepare_optimization_data(
        symbols,
        start_date,
        end_date,
        frequency='M'
    )
    
    if not data.get('valid', False):
        print("❌ Data validation failed")
        if 'validation' in data:
            print(f"Issues: {data['validation'].get('issues', [])}")
        return False, []
    
    print(f"\n✅ Data Service Test Passed")
    print(f"  Valid symbols: {len(data['symbols'])}")
    print(f"  Returns shape: {data['returns'].shape}")
    print(f"  Date range: {data['start_date']} to {data['end_date']}")
    
    return True, data


def test_optimizer_creation(data):
    """Test optimizer creation"""
    print_separator("TEST 2: Optimizer Creation")
    
    if not data or not data.get('valid'):
        print("❌ No valid data for optimizer")
        return False, None
    
    try:
        # Create optimizer from returns data
        optimizer = EnhancedPortfolioOptimizer(
            data['returns'],
            risk_free_rate=0.02
        )
        
        print(f"✅ Optimizer Created Successfully")
        print(f"  Assets: {optimizer.n_assets}")
        print(f"  Periods: {len(optimizer.returns)}")
        print(f"  Symbols: {', '.join(optimizer.symbols)}")
        
        return True, optimizer
        
    except Exception as e:
        print(f"❌ Optimizer creation failed: {e}")
        return False, None


def test_max_sharpe(optimizer):
    """Test Max Sharpe Ratio optimization"""
    print_separator("TEST 3: Max Sharpe Ratio")
    
    if optimizer is None:
        print("❌ No optimizer available")
        return False
    
    try:
        weights = optimizer.max_sharpe_ratio()
        
        if weights is None:
            print("❌ Optimization failed")
            return False
        
        # Get performance metrics
        perf = optimizer.portfolio_performance(weights)
        
        print("✅ Max Sharpe Optimization Successful")
        print(f"\nOptimal Weights:")
        weights_df = optimizer.get_weights_dataframe(weights)
        for _, row in weights_df.iterrows():
            if row['weight'] > 0.01:  # Only show >1%
                print(f"  {row['symbol']:12s} {row['weight']*100:6.2f}%")
        
        print(f"\nPortfolio Metrics:")
        print(f"  Expected Return: {perf['return']*100:6.2f}%")
        print(f"  Volatility:      {perf['volatility']*100:6.2f}%")
        print(f"  Sharpe Ratio:    {perf['sharpe']:6.2f}")
        print(f"  Sortino Ratio:   {perf['sortino']:6.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Max Sharpe test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_min_volatility(optimizer):
    """Test Minimum Volatility optimization"""
    print_separator("TEST 4: Minimum Volatility")
    
    if optimizer is None:
        print("❌ No optimizer available")
        return False
    
    try:
        weights = optimizer.min_volatility()
        
        if weights is None:
            print("❌ Optimization failed")
            return False
        
        perf = optimizer.portfolio_performance(weights)
        
        print("✅ Min Volatility Optimization Successful")
        print(f"\nOptimal Weights:")
        weights_df = optimizer.get_weights_dataframe(weights)
        for _, row in weights_df.iterrows():
            if row['weight'] > 0.01:
                print(f"  {row['symbol']:12s} {row['weight']*100:6.2f}%")
        
        print(f"\nPortfolio Metrics:")
        print(f"  Expected Return: {perf['return']*100:6.2f}%")
        print(f"  Volatility:      {perf['volatility']*100:6.2f}%")
        print(f"  Sharpe Ratio:    {perf['sharpe']:6.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Min Volatility test failed: {e}")
        return False


def test_risk_parity(optimizer):
    """Test Risk Parity optimization"""
    print_separator("TEST 5: Risk Parity")
    
    if optimizer is None:
        print("❌ No optimizer available")
        return False
    
    try:
        weights = optimizer.risk_parity_optimization()
        
        if weights is None:
            print("❌ Optimization failed")
            return False
        
        perf = optimizer.portfolio_performance(weights)
        
        print("✅ Risk Parity Optimization Successful")
        print(f"\nOptimal Weights:")
        weights_df = optimizer.get_weights_dataframe(weights)
        for _, row in weights_df.iterrows():
            if row['weight'] > 0.01:
                print(f"  {row['symbol']:12s} {row['weight']*100:6.2f}%")
        
        print(f"\nPortfolio Metrics:")
        print(f"  Expected Return: {perf['return']*100:6.2f}%")
        print(f"  Volatility:      {perf['volatility']*100:6.2f}%")
        print(f"  Sharpe Ratio:    {perf['sharpe']:6.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Risk Parity test failed: {e}")
        return False


def test_hrp(optimizer):
    """Test Hierarchical Risk Parity optimization"""
    print_separator("TEST 6: Hierarchical Risk Parity (HRP)")
    
    if optimizer is None:
        print("❌ No optimizer available")
        return False
    
    try:
        weights = optimizer.hierarchical_risk_parity()
        
        if weights is None:
            print("❌ Optimization failed")
            return False
        
        perf = optimizer.portfolio_performance(weights)
        
        print("✅ HRP Optimization Successful")
        print(f"\nOptimal Weights:")
        weights_df = optimizer.get_weights_dataframe(weights)
        for _, row in weights_df.iterrows():
            if row['weight'] > 0.01:
                print(f"  {row['symbol']:12s} {row['weight']*100:6.2f}%")
        
        print(f"\nPortfolio Metrics:")
        print(f"  Expected Return: {perf['return']*100:6.2f}%")
        print(f"  Volatility:      {perf['volatility']*100:6.2f}%")
        print(f"  Sharpe Ratio:    {perf['sharpe']:6.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ HRP test failed: {e}")
        return False


def test_efficient_frontier(optimizer):
    """Test Efficient Frontier calculation"""
    print_separator("TEST 7: Efficient Frontier")
    
    if optimizer is None:
        print("❌ No optimizer available")
        return False
    
    try:
        print("Calculating efficient frontier (this may take a moment)...")
        
        frontier = optimizer.efficient_frontier(n_points=20)
        
        if frontier is None or frontier.empty:
            print("❌ Frontier calculation failed")
            return False
        
        print(f"✅ Efficient Frontier Calculated")
        print(f"  Points: {len(frontier)}")
        print(f"  Return range: {frontier['return'].min()*100:.2f}% to {frontier['return'].max()*100:.2f}%")
        print(f"  Volatility range: {frontier['volatility'].min()*100:.2f}% to {frontier['volatility'].max()*100:.2f}%")
        
        # Show first few points
        print(f"\nFirst 5 frontier points:")
        print(frontier[['return', 'volatility']].head().to_string(index=False))
        
        return True
        
    except Exception as e:
        print(f"❌ Efficient Frontier test failed: {e}")
        return False


def test_risk_calculator():
    """Test Risk Metrics Calculator"""
    print_separator("TEST 8: Risk Metrics Calculator")
    
    # Find a valid symbol
    symbols = find_valid_test_symbols()
    
    if not symbols:
        print("❌ No valid symbols found")
        return False
    
    symbol = symbols[0]
    print(f"Testing with symbol: {symbol}")
    
    try:
        # Create calculator
        calculator = create_risk_calculator(risk_free_rate=0.02)
        
        # Calculate metrics for 1 year
        print(f"\nCalculating 1-year risk metrics...")
        metrics = calculator.calculate_all_metrics(symbol, period_years=1, period_label='1y')
        
        if not metrics:
            print("❌ Could not calculate metrics")
            return False
        
        print("✅ Risk Metrics Calculated Successfully")
        print(f"\nMetrics for {symbol} (1 year):")
        print(f"  Volatility:        {metrics['volatility']*100:.2f}%")
        print(f"  Max Drawdown:      {metrics['max_drawdown']*100:.2f}%")
        print(f"  Sharpe Ratio:      {metrics['sharpe_ratio']:.2f}")
        print(f"  Sortino Ratio:     {metrics['sortino_ratio']:.2f}")
        print(f"  Calmar Ratio:      {metrics['calmar_ratio']:.2f}")
        print(f"  VaR (95%):         {metrics['var_95']*100:.2f}%")
        print(f"  CVaR (95%):        {metrics['cvar_95']*100:.2f}%")
        print(f"  Skewness:          {metrics['skewness']:.2f}")
        print(f"  Kurtosis:          {metrics['kurtosis']:.2f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Risk Calculator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_factory_functions():
    """Test factory functions"""
    print_separator("TEST 9: Factory Functions")
    
    symbols = find_valid_test_symbols()
    
    if len(symbols) < 2:
        print("❌ Not enough valid symbols")
        return False
    
    try:
        # Test create_optimizer factory
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=365)
        
        print(f"Creating optimizer via factory function...")
        print(f"Symbols: {', '.join(symbols[:2])}")
        
        optimizer = create_optimizer(
            symbols[:2],
            start_date,
            end_date,
            risk_free_rate=0.02,
            frequency='M'
        )
        
        if optimizer is None:
            print("❌ Factory function returned None")
            return False
        
        print("✅ Factory Functions Work")
        print(f"  Created optimizer with {optimizer.n_assets} assets")
        
        return True
        
    except Exception as e:
        print(f"❌ Factory function test failed: {e}")
        return False


def run_all_tests():
    """Run all Phase 2 tests"""
    print("""
╔═══════════════════════════════════════════════════════════════════╗
║                                                                   ║
║   PORTFOLIO OPTIMIZER - PHASE 2 TEST SUITE                       ║
║   Optimizer & Risk Calculator                                    ║
║                                                                   ║
╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Data Service
    result = test_data_service()
    if result[0]:
        tests_passed += 1
        data = result[1]
    else:
        tests_failed += 1
        print("\n❌ CRITICAL: Data service failed. Cannot continue.")
        return
    
    # Test 2: Optimizer Creation
    result = test_optimizer_creation(data)
    if result[0]:
        tests_passed += 1
        optimizer = result[1]
    else:
        tests_failed += 1
        optimizer = None
    
    # Test 3: Max Sharpe
    if test_max_sharpe(optimizer):
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 4: Min Volatility
    if test_min_volatility(optimizer):
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 5: Risk Parity
    if test_risk_parity(optimizer):
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 6: HRP
    if test_hrp(optimizer):
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 7: Efficient Frontier
    if test_efficient_frontier(optimizer):
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 8: Risk Calculator
    if test_risk_calculator():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Test 9: Factory Functions
    if test_factory_functions():
        tests_passed += 1
    else:
        tests_failed += 1
    
    # Summary
    print_separator("TEST SUMMARY")
    print(f"Tests Passed: {tests_passed}")
    print(f"Tests Failed: {tests_failed}")
    print(f"Total Tests:  {tests_passed + tests_failed}")
    
    if tests_failed == 0:
        print("\n✅✅✅ ALL TESTS PASSED! ✅✅✅")
        print("\nOptimizer and Risk Calculator are working correctly!")
        print("Ready to proceed to Phase 3 (FastAPI Backend)")
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
