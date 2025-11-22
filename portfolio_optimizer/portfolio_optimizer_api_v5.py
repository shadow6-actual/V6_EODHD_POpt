# Portfolio Optimization API - Database V5 Enhanced Integration
# This version integrates directly with your existing DatabaseV5_Enhanced module

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import traceback
import sys
from pathlib import Path

# Add your project directory to path if needed
# sys.path.insert(0, str(Path(__file__).parent.parent))

# Import your existing modules
try:
    from DatabaseV5_Enhanced import (
        session_scope, Asset, AssetPrice, RiskMetrics,
        Session, setup_engine, DB_FILE
    )
    from EnhancedPortfolioOptimizer import EnhancedPortfolioOptimizer
    USE_EXISTING_DB = True
except ImportError as e:
    print(f"WARNING: Could not import existing modules: {e}")
    print("Falling back to standalone mode. Please ensure DatabaseV5_Enhanced.py is in the same directory.")
    USE_EXISTING_DB = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# FLASK APP CONFIGURATION
# ============================================================================

app = Flask(__name__, static_folder='static')
CORS(app)  # Enable CORS for frontend

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

if USE_EXISTING_DB:
    # Use your existing database setup
    logger.info("Initializing with existing DatabaseV5_Enhanced module")
    
    # Initialize the engine and Session
    try:
        engine = setup_engine(DB_FILE)
        from sqlalchemy.orm import sessionmaker
        SessionLocal = sessionmaker(bind=engine, future=True)
        
        # Update the global Session in DatabaseV5_Enhanced
        import DatabaseV5_Enhanced
        DatabaseV5_Enhanced.Session = SessionLocal
        
        logger.info(f"✓ Database initialized: {DB_FILE}")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
else:
    logger.error("Could not initialize database - missing DatabaseV5_Enhanced module")
    logger.error("Please ensure DatabaseV5_Enhanced.py and EnhancedPortfolioOptimizer.py are available")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_asset_returns(session, symbols, start_date, end_date):
    """
    Fetch returns data from database for multiple symbols
    Uses your existing database schema
    """
    data = {}
    
    for symbol in symbols:
        try:
            # Query price data using your AssetPrice model
            results = (
                session.query(AssetPrice.date, AssetPrice.adjclose)
                .filter(
                    AssetPrice.symbol == symbol,
                    AssetPrice.date >= start_date,
                    AssetPrice.date <= end_date
                )
                .order_by(AssetPrice.date)
                .all()
            )
            
            if results and len(results) >= 12:  # Minimum 12 months
                df = pd.DataFrame(results, columns=['date', 'adjclose'])
                df['date'] = pd.to_datetime(df['date'])
                df = df.set_index('date')
                data[symbol] = df['adjclose']
            else:
                logger.warning(f"Insufficient data for {symbol}: {len(results) if results else 0} records")
                
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
    
    if not data:
        return pd.DataFrame()
    
    # Combine and calculate returns
    prices_df = pd.DataFrame(data)
    
    # Handle missing data - forward fill then drop any remaining NaN
    prices_df = prices_df.fillna(method='ffill').dropna()
    
    # Resample to monthly and calculate returns
    monthly_prices = prices_df.resample('M').last()
    returns_df = monthly_prices.pct_change().dropna()
    
    return returns_df

def calculate_portfolio_metrics(optimizer, weights, symbols):
    """Calculate comprehensive portfolio metrics"""
    perf = optimizer.portfolio_performance(weights)
    
    # Calculate additional metrics
    portfolio_returns = optimizer.returns @ weights
    
    # Value at Risk
    var_95 = np.percentile(portfolio_returns, 5)
    
    # Conditional VaR
    cvar_95 = portfolio_returns[portfolio_returns <= var_95].mean()
    
    # Maximum Drawdown
    cumulative = (1 + portfolio_returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    max_drawdown = drawdown.min()
    
    # Calmar Ratio
    annual_return = perf['return']
    calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
    
    return {
        'return': float(perf['return']),
        'volatility': float(perf['volatility']),
        'sharpe_ratio': float(perf['sharpe']),
        'sortino_ratio': float(perf['sortino']),
        'max_drawdown': float(abs(max_drawdown)),
        'calmar_ratio': float(calmar_ratio),
        'var_95': float(abs(var_95)),
        'cvar_95': float(abs(cvar_95)),
        'weights': {symbols[i]: float(weights[i]) for i in range(len(symbols))}
    }

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_from_directory('static', 'index.html')

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'database': 'connected' if USE_EXISTING_DB else 'not_configured',
        'version': '1.0.0'
    })

@app.route('/api/search_assets', methods=['GET'])
def search_assets():
    """Search for assets by symbol or name"""
    if not USE_EXISTING_DB:
        return jsonify({'error': 'Database not configured'}), 500
    
    query = request.args.get('query', '').upper()
    limit = int(request.args.get('limit', 20))
    
    if len(query) < 1:
        return jsonify({'assets': []})
    
    try:
        with session_scope() as session:
            # Search by symbol or name using your Asset model
            assets = session.query(Asset).filter(
                Asset.is_active == True,
                (Asset.symbol.like(f'%{query}%') | Asset.name.like(f'%{query}%'))
            ).limit(limit).all()
            
            results = [{
                'symbol': asset.symbol,
                'name': asset.name or '',
                'exchange': asset.exchange or '',
                'type': asset.asset_type or '',
                'currency': asset.currency or 'USD'
            } for asset in assets]
            
            return jsonify({'assets': results})
            
    except Exception as e:
        logger.error(f"Error searching assets: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/asset_info', methods=['POST'])
def get_asset_info():
    """Get detailed information about specific assets"""
    if not USE_EXISTING_DB:
        return jsonify({'error': 'Database not configured'}), 500
    
    data = request.json
    symbols = data.get('symbols', [])
    period = data.get('period', '5y')
    
    try:
        with session_scope() as session:
            results = {}
            
            for symbol in symbols:
                # Get asset info
                asset = session.query(Asset).filter_by(symbol=symbol).first()
                if not asset:
                    continue
                
                # Get risk metrics (if available)
                risk_metrics = session.query(RiskMetrics).filter_by(
                    symbol=symbol,
                    period=period
                ).first()
                
                # Get latest price
                latest_price = session.query(AssetPrice).filter_by(
                    symbol=symbol
                ).order_by(AssetPrice.date.desc()).first()
                
                results[symbol] = {
                    'name': asset.name or symbol,
                    'exchange': asset.exchange,
                    'type': asset.asset_type,
                    'latest_price': float(latest_price.adjclose) if latest_price else None,
                    'latest_date': latest_price.date.isoformat() if latest_price else None,
                    'metrics': {
                        'volatility': float(risk_metrics.volatility) if risk_metrics and risk_metrics.volatility else None,
                        'sharpe_ratio': float(risk_metrics.sharpe_ratio) if risk_metrics and risk_metrics.sharpe_ratio else None,
                        'sortino_ratio': float(risk_metrics.sortino_ratio) if risk_metrics and risk_metrics.sortino_ratio else None,
                        'max_drawdown': float(risk_metrics.max_drawdown) if risk_metrics and risk_metrics.max_drawdown else None,
                    } if risk_metrics else None
                }
            
            return jsonify({'assets': results})
            
    except Exception as e:
        logger.error(f"Error getting asset info: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/optimize', methods=['POST'])
def optimize_portfolio():
    """Run portfolio optimization"""
    if not USE_EXISTING_DB:
        return jsonify({'error': 'Database not configured'}), 500
    
    data = request.json
    
    symbols = data.get('symbols', [])
    method = data.get('method', 'max_sharpe')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    risk_free_rate = float(data.get('risk_free_rate', 0.02))
    constraints = data.get('constraints', {})
    
    # Validate inputs
    if not symbols or len(symbols) < 2:
        return jsonify({'error': 'Please select at least 2 assets'}), 400
    
    try:
        # Parse dates
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
        else:
            start_dt = datetime.now() - relativedelta(years=5)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date)
        else:
            end_dt = datetime.now()
        
        # Fetch data using your database
        with session_scope() as session:
            returns = get_asset_returns(session, symbols, start_dt.date(), end_dt.date())
        
        if returns.empty:
            return jsonify({'error': 'No data available for selected assets and time period'}), 400
        
        # Filter symbols that have data
        available_symbols = list(returns.columns)
        if len(available_symbols) < len(symbols):
            missing = set(symbols) - set(available_symbols)
            logger.warning(f"Missing data for symbols: {missing}")
        
        if len(available_symbols) < 2:
            return jsonify({'error': 'Insufficient data for optimization'}), 400
        
        # Initialize optimizer (uses your EnhancedPortfolioOptimizer)
        optimizer = EnhancedPortfolioOptimizer(returns, risk_free_rate=risk_free_rate)
        
        # Build constraints list
        scipy_constraints = []
        
        # Run optimization based on selected method
        if method == 'max_sharpe':
            weights = optimizer.max_sharpe_ratio(scipy_constraints if scipy_constraints else None)
            method_name = "Maximum Sharpe Ratio"
        elif method == 'min_volatility':
            weights = optimizer.min_volatility(scipy_constraints if scipy_constraints else None)
            method_name = "Minimum Volatility"
        elif method == 'risk_parity':
            weights = optimizer.risk_parity_optimization()
            method_name = "Risk Parity"
        elif method == 'hrp':
            weights = optimizer.hierarchical_risk_parity()
            method_name = "Hierarchical Risk Parity"
        elif method == 'max_return':
            max_vol = float(constraints.get('max_volatility', 0.15))
            weights = optimizer.max_return(max_vol, scipy_constraints if scipy_constraints else None)
            method_name = "Maximum Return"
        else:
            return jsonify({'error': f'Unknown optimization method: {method}'}), 400
        
        if weights is None:
            return jsonify({'error': 'Optimization failed to converge'}), 400
        
        # Calculate metrics
        metrics = calculate_portfolio_metrics(optimizer, weights, available_symbols)
        
        # Calculate efficient frontier (if requested)
        frontier_data = None
        if data.get('include_frontier', False):
            try:
                frontier_df = optimizer.efficient_frontier(n_points=50)
                if frontier_df is not None:
                    frontier_data = {
                        'returns': frontier_df['return'].tolist(),
                        'volatilities': frontier_df['volatility'].tolist()
                    }
            except Exception as e:
                logger.warning(f"Could not calculate efficient frontier: {e}")
        
        return jsonify({
            'success': True,
            'method': method_name,
            'metrics': metrics,
            'frontier': frontier_data,
            'period': {
                'start': start_dt.date().isoformat(),
                'end': end_dt.date().isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Optimization error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/efficient_frontier', methods=['POST'])
def calculate_efficient_frontier():
    """Calculate efficient frontier for given assets"""
    if not USE_EXISTING_DB:
        return jsonify({'error': 'Database not configured'}), 500
    
    data = request.json
    
    symbols = data.get('symbols', [])
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    risk_free_rate = float(data.get('risk_free_rate', 0.02))
    n_points = int(data.get('n_points', 100))
    
    if not symbols or len(symbols) < 2:
        return jsonify({'error': 'Please select at least 2 assets'}), 400
    
    try:
        # Parse dates
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
        else:
            start_dt = datetime.now() - relativedelta(years=5)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date)
        else:
            end_dt = datetime.now()
        
        # Fetch data
        with session_scope() as session:
            returns = get_asset_returns(session, symbols, start_dt.date(), end_dt.date())
        
        if returns.empty or len(returns.columns) < 2:
            return jsonify({'error': 'Insufficient data for analysis'}), 400
        
        # Initialize optimizer
        optimizer = EnhancedPortfolioOptimizer(returns, risk_free_rate=risk_free_rate)
        
        # Calculate frontier
        frontier_df = optimizer.efficient_frontier(n_points=n_points)
        
        if frontier_df is None:
            return jsonify({'error': 'Failed to calculate efficient frontier'}), 400
        
        # Calculate key portfolios
        min_vol_weights = optimizer.min_volatility()
        max_sharpe_weights = optimizer.max_sharpe_ratio()
        
        available_symbols = list(returns.columns)
        
        return jsonify({
            'success': True,
            'frontier': {
                'returns': frontier_df['return'].tolist(),
                'volatilities': frontier_df['volatility'].tolist()
            },
            'portfolios': {
                'min_volatility': calculate_portfolio_metrics(optimizer, min_vol_weights, available_symbols),
                'max_sharpe': calculate_portfolio_metrics(optimizer, max_sharpe_weights, available_symbols)
            }
        })
        
    except Exception as e:
        logger.error(f"Efficient frontier error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@app.route('/api/correlation_matrix', methods=['POST'])
def get_correlation_matrix():
    """Get correlation matrix for selected assets"""
    if not USE_EXISTING_DB:
        return jsonify({'error': 'Database not configured'}), 500
    
    data = request.json
    
    symbols = data.get('symbols', [])
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    if not symbols:
        return jsonify({'error': 'No symbols provided'}), 400
    
    try:
        # Parse dates
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
        else:
            start_dt = datetime.now() - relativedelta(years=5)
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date)
        else:
            end_dt = datetime.now()
        
        # Fetch data
        with session_scope() as session:
            returns = get_asset_returns(session, symbols, start_dt.date(), end_dt.date())
        
        if returns.empty:
            return jsonify({'error': 'No data available'}), 400
        
        # Calculate correlation matrix
        corr_matrix = returns.corr()
        
        return jsonify({
            'success': True,
            'symbols': list(corr_matrix.columns),
            'correlation': corr_matrix.values.tolist()
        })
        
    except Exception as e:
        logger.error(f"Correlation matrix error: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    # Create static folder if it doesn't exist
    import os
    os.makedirs('static', exist_ok=True)
    
    if not USE_EXISTING_DB:
        logger.error("=" * 70)
        logger.error("ERROR: Database modules not found!")
        logger.error("=" * 70)
        logger.error("Please ensure the following files are in your project directory:")
        logger.error("  - DatabaseV5_Enhanced.py")
        logger.error("  - EnhancedPortfolioOptimizer.py")
        logger.error("")
        logger.error("Or update sys.path in this file to point to their location.")
        logger.error("=" * 70)
        sys.exit(1)
    
    # Run the Flask app
    logger.info("=" * 70)
    logger.info("🚀 Portfolio Optimizer API Starting")
    logger.info("=" * 70)
    logger.info(f"✓ Database: {DB_FILE}")
    logger.info(f"✓ Server: http://localhost:5000")
    logger.info("=" * 70)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
