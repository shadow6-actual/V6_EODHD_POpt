# webapp/app.py
# PURPOSE: Main entry point. Handles API requests, connects UI to DataManager and Optimizer.

import os
import sys
import logging
import json
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, g

import sentry_sdk

if os.getenv('SENTRY_DSN'):
    sentry_sdk.init(
        dsn=os.getenv('SENTRY_DSN'),
        traces_sample_rate=0.1
    )
    
# Auth imports
from webapp.auth import require_auth, optional_auth, get_clerk_config

# Subscription imports
from webapp.subscription import (
    get_user_tier, get_user_tier_info, get_tier_config,
    can_access_feature, can_use_optimization_method,
    get_max_assets, can_save_portfolio, get_pricing_data,
    require_feature, require_tier, start_trial, TRIAL_PERIOD_DAYS
)

# 1. SETUP PATHS & LOGGING
# ============================================================================
CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
sys.path.append(str(PARENT_DIR))

try:
    import config_v6
    from models_v6 import Asset, SavedPortfolio
    from webapp.data_manager import data_manager
    from webapp.optimization_engine import PortfolioOptimizer
except ImportError as e:
    print(f"❌ CRITICAL ERROR: Import failed. {e}")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("WebApp")

# 2. INIT APP
# ============================================================================
app = Flask(__name__)
app.secret_key = "folio_visualizer_v6_secret"

# 3. ROUTES - PAGE VIEWS
# ============================================================================
@app.route('/')
def landing():
    """Renders the landing page."""
    return render_template('landing.html')


@app.route('/app')
def index():
    """Renders the main dashboard/optimizer."""
    clerk_config = get_clerk_config()
    return render_template('index.html', clerk_config=clerk_config)


@app.route('/pricing')
def pricing():
    """Renders the pricing page."""
    pricing_data = get_pricing_data()
    clerk_config = get_clerk_config()
    return render_template('pricing.html', pricing=pricing_data, clerk_config=clerk_config)


# 3a. AUTH ROUTES
# ============================================================================
@app.route('/api/auth/config')
def auth_config():
    """Return Clerk configuration for frontend"""
    return jsonify(get_clerk_config())


@app.route('/api/auth/me')
@require_auth
def auth_me():
    """Get current user info including subscription tier"""
    from webapp.user_models import get_or_create_user, User
    
    try:
        with data_manager._get_session() as session:
            # Get or create local user record
            user = get_or_create_user(session, g.user_id, g.username)
            
            # Store user object in g for downstream use
            g.user_obj = user
            
            # Get tier info
            tier_info = get_user_tier_info(user)
            
            return jsonify({
                'user_id': g.user_id,
                'username': g.username,
                'local_user': user.to_dict(),
                'subscription': tier_info
            })
    except Exception as e:
        logger.error(f"Auth me error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/auth/sync', methods=['POST'])
@require_auth
def auth_sync():
    """Sync user data from Clerk to local database"""
    from webapp.user_models import get_or_create_user
    
    try:
        with data_manager._get_session() as session:
            user = get_or_create_user(session, g.user_id, g.username)
            g.user_obj = user
            tier_info = get_user_tier_info(user)
            
            return jsonify({
                'message': 'User synced successfully',
                'user': user.to_dict(),
                'subscription': tier_info
            })
    except Exception as e:
        logger.error(f"Auth sync error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/subscription/start-trial', methods=['POST'])
@require_auth
def start_free_trial():
    """Start a free Pro trial for the current user"""
    from webapp.user_models import get_or_create_user
    
    try:
        with data_manager._get_session() as session:
            user = get_or_create_user(session, g.user_id, g.username)
            
            # Check if user already used trial or has a paid subscription
            if user.subscription_tier in ['premium', 'pro']:
                return jsonify({
                    'error': 'already_subscribed',
                    'message': 'You already have an active subscription!'
                }), 400
            
            if user.subscription_tier == 'trial':
                return jsonify({
                    'error': 'trial_active',
                    'message': 'You already have an active trial!'
                }), 400
            
            # Start the trial
            success = start_trial(session, user)
            
            if success:
                tier_info = get_user_tier_info(user)
                return jsonify({
                    'message': f'🎉 Your {TRIAL_PERIOD_DAYS}-day Pro trial has started!',
                    'subscription': tier_info
                })
            else:
                return jsonify({
                    'error': 'trial_failed',
                    'message': 'Unable to start trial. Please contact support.'
                }), 400
                
    except Exception as e:
        logger.error(f"Start trial error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/admin/set-tier', methods=['POST'])
@require_auth
def admin_set_tier():
    """
    ADMIN ONLY: Set subscription tier for testing.
    In production, remove this or add proper admin authentication.
    
    POST body: { "tier": "free|premium|pro|trial", "days": 30 }
    """
    from webapp.user_models import get_or_create_user
    
    # TODO: Add proper admin check (e.g., check if user is in admin list)
    ADMIN_USERNAMES = ['shadow6']  # Add your admin username(s) here
    
    try:
        with data_manager._get_session() as session:
            user = get_or_create_user(session, g.user_id, g.username)
            
            # Check if user is admin
            if user.username not in ADMIN_USERNAMES:
                return jsonify({'error': 'Unauthorized'}), 403
            
            data = request.json
            new_tier = data.get('tier', 'free')
            days = data.get('days', 30)
            
            if new_tier not in ['free', 'premium', 'pro', 'trial']:
                return jsonify({'error': 'Invalid tier'}), 400
            
            user.subscription_tier = new_tier
            
            if new_tier != 'free':
                user.subscription_expires_at = datetime.utcnow() + timedelta(days=days)
            else:
                user.subscription_expires_at = None
            
            session.commit()
            
            tier_info = get_user_tier_info(user)
            return jsonify({
                'message': f'Tier set to {new_tier} for {days} days',
                'subscription': tier_info
            })
            
    except Exception as e:
        logger.error(f"Admin set tier error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/subscription/info')
@optional_auth
def subscription_info():
    """Get current user's subscription info (works for anonymous too)"""
    from webapp.user_models import get_user_by_clerk_id
    
    user = None
    if g.user_id:
        try:
            with data_manager._get_session() as session:
                user = get_user_by_clerk_id(session, g.user_id)
        except:
            pass
    
    tier_info = get_user_tier_info(user)
    return jsonify(tier_info)


# 4. ROUTES - API ENDPOINTS
# ============================================================================

@app.route('/api/search')
def search_assets():
    """Smart Search: Prioritizes Exact Matches > Starts With > US Assets > Others."""
    query = request.args.get('q', '').strip().upper()
    if not query or len(query) < 1:
        return jsonify([])

    try:
        with data_manager._get_session() as session:
            results = session.query(Asset)\
                .filter(
                    (Asset.symbol.ilike(f"%{query}%")) | 
                    (Asset.name.ilike(f"%{query}%"))
                )\
                .filter(Asset.is_active == True)\
                .limit(50)\
                .all()
            
            hits = []
            for r in results:
                hits.append({
                    'symbol': r.symbol,
                    'name': r.name,
                    'exchange': r.exchange,
                    'type': r.asset_type
                })

            def rank_score(asset):
                sym = asset['symbol']
                base_sym = sym.split('.')[0]
                exact_base = (base_sym == query)
                starts_with = sym.startswith(query)
                is_us = asset['exchange'] in ['US', 'NYSE', 'NASDAQ', 'AMEX']
                return (not exact_base, not starts_with, not is_us, len(sym), sym)

            hits.sort(key=rank_score)
            return jsonify(hits[:10])

    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/asset-metadata', methods=['POST'])
def get_asset_metadata():
    """Get asset metadata including group classifications"""
    try:
        data = request.json
        tickers = data.get('tickers', [])
        
        if not tickers:
            return jsonify({'error': 'No tickers provided'}), 400
        
        # Fetch metadata from data_manager
        metadata = data_manager.get_asset_metadata(tickers)
        
        if not metadata:
            return jsonify({'error': 'No metadata found'}), 404
        
        # Build group summary
        group_summary = {}
        for ticker, info in metadata.items():
            group = info['group']
            if group not in group_summary:
                group_summary[group] = {'count': 0, 'tickers': []}
            group_summary[group]['count'] += 1
            group_summary[group]['tickers'].append(ticker)
        
        return jsonify({
            'metadata': metadata,
            'group_summary': group_summary
        })
        
    except Exception as e:
        logger.error(f"Error fetching asset metadata: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/available-groups', methods=['GET'])
def get_available_groups():
    """Get list of all possible asset groups"""
    try:
        # Get mapping from data_manager
        asset_type_mapping = data_manager.ASSET_TYPE_TO_GROUP
        
        # Build reverse mapping
        group_descriptions = {}
        for asset_type, group in asset_type_mapping.items():
            if group not in group_descriptions:
                group_descriptions[group] = []
            group_descriptions[group].append(asset_type)
        
        # Format descriptions
        formatted_descriptions = {
            group: ', '.join(sorted(types)) 
            for group, types in group_descriptions.items()
        }
        
        return jsonify({
            'groups': sorted(group_descriptions.keys()),
            'descriptions': formatted_descriptions
        })
        
    except Exception as e:
        logger.error(f"Error fetching available groups: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/optimize', methods=['POST'])
@optional_auth
def run_optimization():
    """Run portfolio optimization with tier-based restrictions"""
    from webapp.user_models import get_user_by_clerk_id
    
    # Get user for tier checking
    user = None
    if g.user_id:
        try:
            with data_manager._get_session() as session:
                user = get_user_by_clerk_id(session, g.user_id)
        except:
            pass
    
    data = request.json
    tickers = data.get('tickers', [])
    user_weights = data.get('user_weights', {})
    constraints = data.get('constraints', {})
    opt_goal = data.get('optimization_goal', 'max_sharpe')
    target_return = data.get('target_return')
    target_volatility = data.get('target_volatility')
    benchmark_ticker = data.get('benchmark', 'SPY.US')
    user_benchmark_id = data.get('user_benchmark_id')
    use_group_constraints = data.get('use_group_constraints', False)
    group_constraints_input = data.get('group_constraints', {})
    include_diversification = data.get('include_diversification', True)
    
    req_start_str = data.get('start_date', '2015-01-01')
    try:
        req_start = datetime.strptime(req_start_str, '%Y-%m-%d').date()
    except:
        req_start = datetime(2018, 1, 1).date()

    end_date = data.get('end_date')

    if not tickers:
        return jsonify({'error': 'No tickers provided'}), 400

    # =========================================================================
    # TIER-BASED RESTRICTIONS
    # =========================================================================
    
    # Check asset limit
    max_assets = get_max_assets(user)
    if len(tickers) > max_assets:
        tier = get_user_tier(user)
        return jsonify({
            'error': 'asset_limit_exceeded',
            'message': f'Your {tier.title()} plan allows up to {max_assets} assets. You have {len(tickers)}.',
            'current_tier': tier,
            'max_assets': max_assets,
            'upgrade_required': True
        }), 403
    
    # Check optimization method access
    allowed, reason = can_use_optimization_method(user, opt_goal)
    if not allowed:
        tier = get_user_tier(user)
        return jsonify({
            'error': 'method_not_allowed',
            'message': reason,
            'current_tier': tier,
            'upgrade_required': True
        }), 403
    
    # Check group constraints access (Pro only)
    if use_group_constraints and group_constraints_input:
        if not can_access_feature(user, 'group_constraints'):
            tier = get_user_tier(user)
            return jsonify({
                'error': 'feature_not_allowed',
                'message': 'Group constraints require Pro subscription',
                'feature': 'group_constraints',
                'current_tier': tier,
                'upgrade_required': True
            }), 403
    
    # Check diversification analytics access (Pro only)
    if include_diversification:
        if not can_access_feature(user, 'diversification_analytics'):
            # Don't error - just disable the feature silently
            include_diversification = False

    logger.info(f"Optimization: {opt_goal} for {tickers}")

    try:
        # A. COVERAGE CHECK
        coverage = data_manager.get_ticker_coverage(tickers)
        if not coverage:
             return jsonify({'error': 'No data found for these tickers in database.'}), 404

        max_min_date = max(info['start'] for info in coverage.values())
        if req_start < max_min_date:
            bad_actors = [f"{t} (starts {info['start']})" for t, info in coverage.items() if info['start'] > req_start]
            msg = f"Data Gap: Requested {req_start_str}, but earliest common date is {max_min_date}.\nLimiting: {', '.join(bad_actors)}"
            return jsonify({
                'error': 'coverage_gap',
                'message': msg,
                'suggested_start_date': max_min_date.strftime('%Y-%m-%d'),
                'details': bad_actors
            }), 400

        # B. FETCH DATA
        # For tracking error methods, auto-include benchmark in data fetch
        fetch_tickers = tickers.copy()
        is_tracking_error_method = opt_goal in ['min_tracking_error', 'max_information_ratio', 'max_excess_return_target_te']
        
        # Always add benchmark if specified (for both tracking error AND comparison)
        if benchmark_ticker and benchmark_ticker not in fetch_tickers:
            fetch_tickers.append(benchmark_ticker)
            logger.info(f"Auto-added benchmark {benchmark_ticker} for comparison")
        
        df = data_manager.get_price_history(fetch_tickers, start_date=req_start_str, end_date=end_date)
        if df.empty:
            return jsonify({'error': 'No data found for the selected tickers/dates'}), 404

        # C1. PREPARE GROUP CONSTRAINTS (NEW)
        group_constraints = None
        ticker_groups = None
        
        if use_group_constraints and group_constraints_input:
            # Fetch asset metadata to get groups
            metadata = data_manager.get_asset_metadata(tickers)
            
            # Build ticker -> group mapping
            ticker_groups = {
                ticker: metadata[ticker]['group'] 
                for ticker in tickers if ticker in metadata
            }
            
            # Convert percentage inputs to decimals
            group_constraints = {}
            for group, bounds in group_constraints_input.items():
                group_constraints[group] = {
                    'min': bounds.get('min', 0.0) / 100.0,
                    'max': bounds.get('max', 100.0) / 100.0
                }
            
            logger.info(f"Group constraints enabled: {group_constraints}")
            logger.info(f"Ticker groups: {ticker_groups}")

        # C2. RUN OPTIMIZATION
        optimizer = PortfolioOptimizer(
            df,
            group_constraints=group_constraints,
            ticker_groups=ticker_groups
        )
        
        # Run requested optimization method
        if opt_goal == 'max_sharpe':
            optimized = optimizer.optimize_sharpe_ratio(constraints)
        elif opt_goal == 'min_volatility':
            optimized = optimizer.optimize_min_volatility(constraints)
        elif opt_goal == 'min_vol_target_return':
            optimized = optimizer.optimize_min_vol_target_return(target_return, constraints)
        elif opt_goal == 'max_return_target_vol':
            optimized = optimizer.optimize_max_return_target_vol(target_volatility, constraints)
        elif opt_goal == 'risk_parity':
            optimized = optimizer.optimize_risk_parity()
        elif opt_goal == 'equal_weight':
            optimized = optimizer.equal_weight_portfolio()
        elif opt_goal == 'min_cvar':
            optimized = optimizer.optimize_min_cvar(constraints)
        elif opt_goal == 'min_cvar_target_return':
            optimized = optimizer.optimize_min_cvar_target_return(target_return, constraints)
        elif opt_goal == 'max_return_target_cvar':
            target_cvar = data.get('target_cvar')
            optimized = optimizer.optimize_max_return_target_cvar(target_cvar, constraints)
        elif opt_goal == 'min_tracking_error':
            optimized = optimizer.optimize_min_tracking_error(benchmark_ticker, constraints)
        elif opt_goal == 'max_information_ratio':
            optimized = optimizer.optimize_max_information_ratio(benchmark_ticker, constraints)
        elif opt_goal == 'max_excess_return_target_te':
            target_te = data.get('target_tracking_error')
            optimized = optimizer.optimize_max_excess_return_target_te(benchmark_ticker, target_te, constraints)
        elif opt_goal == 'max_kelly':
            optimized = optimizer.optimize_kelly_criterion(constraints)
        elif opt_goal == 'min_drawdown_target_return':
            optimized = optimizer.optimize_min_drawdown_target_return(target_return, constraints)
        elif opt_goal == 'max_omega_target_return':
            optimized = optimizer.optimize_max_omega_target_return(target_return, constraints)
        elif opt_goal == 'max_sortino_target_return':
            optimized = optimizer.optimize_max_sortino_target_return(target_return, constraints)
        elif opt_goal == 'robust_max_sharpe':
            n_resamples = data.get('robust_resamples', 100)
            optimized = optimizer.optimize_robust_sharpe(constraints, n_resamples=n_resamples)
        elif opt_goal == 'robust_min_volatility':
            n_resamples = data.get('robust_resamples', 100)
            optimized = optimizer.optimize_robust_min_volatility(constraints, n_resamples=n_resamples)
        elif opt_goal == 'robust_min_vol_target_return':
            n_resamples = data.get('robust_resamples', 100)
            optimized = optimizer.optimize_robust_min_vol_target_return(target_return, constraints, n_resamples=n_resamples)
        elif opt_goal == 'robust_max_return_target_vol':
            n_resamples = data.get('robust_resamples', 100)
            optimized = optimizer.optimize_robust_max_return_target_vol(target_volatility, constraints, n_resamples=n_resamples)
        else:
            optimized = optimizer.optimize_sharpe_ratio(constraints)
        
        # D. USER'S PROVIDED PORTFOLIO (if weights given)
        user_portfolio = None
        if user_weights:
            # Use only original tickers that actually exist in the data
            user_tickers = [t for t in tickers if t in df.columns]
            
            if len(user_tickers) > 0:
                user_df = df[user_tickers]
                user_optimizer = PortfolioOptimizer(user_df)
                
                # Convert dict to array matching column order
                user_weights_array = np.array([user_weights.get(t, 0) for t in user_tickers])
                
                # Normalize if needed
                if np.sum(user_weights_array) > 0:
                    user_weights_array = user_weights_array / np.sum(user_weights_array)
                    user_portfolio = user_optimizer.calculate_portfolio_stats(user_weights_array)
                    user_portfolio['allocation'] = {t: round(w*100, 2) for t, w in zip(user_tickers, user_weights_array)}

        # E. BENCHMARK PORTFOLIO
        benchmark_portfolio = None
        if user_benchmark_id:
            # Use saved portfolio as benchmark
            try:
                with data_manager._get_sqlite_session() as session:
                    bench_port = session.query(SavedPortfolio).filter_by(id=user_benchmark_id).first()
                    if bench_port:
                        bench_tickers = json.loads(bench_port.tickers)
                        bench_weights_dict = json.loads(bench_port.weights)
                        bench_df = data_manager.get_price_history(bench_tickers, start_date=req_start_str, end_date=end_date)
                        
                        if not bench_df.empty:
                            bench_optimizer = PortfolioOptimizer(bench_df)
                            bench_weights_array = np.array([bench_weights_dict.get(t, 0) for t in bench_tickers])
                            if np.sum(bench_weights_array) > 0:
                                bench_weights_array = bench_weights_array / np.sum(bench_weights_array)
                                benchmark_portfolio = bench_optimizer.calculate_portfolio_stats(bench_weights_array)
                                benchmark_portfolio['name'] = bench_port.name
                                benchmark_portfolio['allocation'] = {t: round(w*100, 2) for t, w in zip(bench_tickers, bench_weights_array)}
            except Exception as e:
                logger.warning(f"Failed to load user benchmark: {e}")
        
        elif benchmark_ticker and benchmark_ticker in df.columns:
            # Use standard benchmark (e.g., SPY.US)
            try:
                bench_df = df[[benchmark_ticker]]
                bench_optimizer = PortfolioOptimizer(bench_df)
                bench_weights = np.array([1.0])  # 100% in benchmark
                benchmark_portfolio = bench_optimizer.calculate_portfolio_stats(bench_weights)
                benchmark_portfolio['name'] = benchmark_ticker
                benchmark_portfolio['allocation'] = {benchmark_ticker: 100.0}
            except Exception as e:
                logger.warning(f"Failed to calculate benchmark {benchmark_ticker}: {e}")
        
        # F. EFFICIENT FRONTIER SCATTER
        frontier_points = []
        for i in range(200):
            weights = np.random.random(len(df.columns))
            weights /= np.sum(weights)
            ret, vol, sharpe = optimizer.performance_stats(weights)
            frontier_points.append({
                'return': round(ret * 100, 2),
                'volatility': round(vol * 100, 2),
                'sharpe': round(sharpe, 2)
            })

        # G. BUILD RESPONSE
        # Calculate diversification metrics if requested AND allowed
        health_score_weights = data.get('health_score_weights', None)
        
        opt_diversification = None
        user_diversification = None
        bench_diversification = None
        
        if include_diversification:
            # For optimized portfolio
            opt_weights_array = np.array([optimized['weights'].get(t, 0) / 100.0 for t in optimizer.tickers])
            opt_diversification = optimizer.calculate_diversification_metrics(opt_weights_array)
            
            # For user portfolio
            if user_portfolio:
                user_weights_array = np.array([user_weights.get(t, 0) for t in optimizer.tickers])
                if np.sum(user_weights_array) > 0:
                    user_weights_array = user_weights_array / np.sum(user_weights_array)
                    user_diversification = optimizer.calculate_diversification_metrics(user_weights_array)
            
            # For benchmark
            if benchmark_portfolio and benchmark_ticker in df.columns:
                bench_weights_array = np.zeros(len(optimizer.tickers))
                if benchmark_ticker in optimizer.tickers:
                    bench_idx = optimizer.tickers.index(benchmark_ticker)
                    bench_weights_array[bench_idx] = 1.0
                    bench_diversification = optimizer.calculate_diversification_metrics(bench_weights_array)

        response = {
            'status': 'success',
            'analysis_period': {
                'start': df.index[0].strftime('%Y-%m-%d'),
                'end': df.index[-1].strftime('%Y-%m-%d'),
                'trading_days': len(df)
            },
            'optimized_portfolio': optimized,
            'user_portfolio': user_portfolio,
            'benchmark_portfolio': benchmark_portfolio,
            'frontier_scatter': frontier_points,
            'correlation_matrix': optimizer.returns.corr().round(2).to_dict(),
            'diversification': {
                'optimized': opt_diversification,
                'user': user_diversification,
                'benchmark': bench_diversification
            } if include_diversification else None,
            'tier_info': {
                'current_tier': get_user_tier(user),
                'diversification_enabled': include_diversification
            }
        }
        
        # Add group allocation breakdown if group constraints were used
        if use_group_constraints and ticker_groups:
            user_group_alloc = {}
            opt_group_alloc = {}
            
            # Calculate group allocations
            for ticker, group in ticker_groups.items():
                if ticker not in user_weights:
                    continue
                    
                if group not in user_group_alloc:
                    user_group_alloc[group] = 0.0
                    opt_group_alloc[group] = 0.0
                
                # User allocation
                user_group_alloc[group] += user_weights[ticker]
                
                # Optimized allocation
                if 'allocation' in optimized and ticker in optimized['allocation']:
                    opt_group_alloc[group] += optimized['allocation'][ticker] / 100.0
            
            # Convert to percentages for display
            response['group_allocations'] = {
                'user': {g: round(v * 100, 2) for g, v in user_group_alloc.items()},
                'optimized': {g: round(v * 100, 2) for g, v in opt_group_alloc.items()},
                'constraints': group_constraints_input  # Original % values
            }
        
        # Sanitize NaN values before JSON serialization
        def sanitize_dict(obj):
            """Recursively replace NaN with 0 in nested dicts"""
            if isinstance(obj, dict):
                return {k: sanitize_dict(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [sanitize_dict(item) for item in obj]
            elif isinstance(obj, float):
                if np.isnan(obj) or np.isinf(obj):
                    return 0.0
                return obj
            return obj
        
        response = sanitize_dict(response)
        
        return jsonify(response)

    except Exception as e:
        logger.error(f"Optimization failed: {e}", exc_info=True)
        return jsonify({'error': f"Optimization failed: {str(e)}"}), 500


@app.route('/api/portfolios', methods=['GET'])
def list_portfolios():
    """List all saved portfolios"""
    try:
        with data_manager._get_sqlite_session() as session:
            portfolios = session.query(SavedPortfolio).order_by(SavedPortfolio.updated_at.desc()).all()
            result = [{
                'id': p.id,
                'name': p.name,
                'created_at': p.created_at.isoformat(),
                'updated_at': p.updated_at.isoformat()
            } for p in portfolios]
            return jsonify(result)
    except Exception as e:
        logger.error(f"List portfolios error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/portfolios/<int:portfolio_id>', methods=['GET'])
def get_portfolio(portfolio_id):
    """Get a specific saved portfolio"""
    try:
        with data_manager._get_sqlite_session() as session:
            portfolio = session.query(SavedPortfolio).filter_by(id=portfolio_id).first()
            if not portfolio:
                return jsonify({'error': 'Portfolio not found'}), 404
            
            return jsonify({
                'id': portfolio.id,
                'name': portfolio.name,
                'tickers': json.loads(portfolio.tickers),
                'weights': json.loads(portfolio.weights),
                'constraints': json.loads(portfolio.constraints) if portfolio.constraints else {},
                'created_at': portfolio.created_at.isoformat(),
                'updated_at': portfolio.updated_at.isoformat()
            })
    except Exception as e:
        logger.error(f"Get portfolio error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/portfolios', methods=['POST'])
@optional_auth
def save_portfolio():
    """Save a new portfolio (requires login, tier limits apply)"""
    from webapp.user_models import get_or_create_user, UserPortfolio, get_user_by_clerk_id
    
    data = request.json
    name = data.get('name')
    tickers = data.get('tickers', [])
    weights = data.get('weights', {})
    constraints = data.get('constraints', {})
    is_public = data.get('is_public', False)
    
    if not name or not tickers:
        return jsonify({'error': 'Name and tickers required'}), 400
    
    # Require login for saving portfolios
    if not g.user_id:
        return jsonify({
            'error': 'login_required',
            'message': 'Please sign in to save portfolios. It\'s free!',
            'upgrade_required': False
        }), 401
    
    try:
        with data_manager._get_session() as session:
            user = get_or_create_user(session, g.user_id, g.username)
            
            # Check portfolio limit
            allowed, reason, current, max_count = can_save_portfolio(session, user)
            if not allowed:
                return jsonify({
                    'error': 'portfolio_limit_exceeded',
                    'message': reason,
                    'current_count': current,
                    'max_count': max_count,
                    'upgrade_required': True
                }), 403
            
            portfolio = UserPortfolio(
                user_id=user.id,
                name=name,
                tickers=tickers,
                weights=weights,
                constraints=constraints if constraints else None,
                is_public=is_public
            )
            session.add(portfolio)
            session.commit()
            
            tier = get_user_tier(user)
            return jsonify({
                'id': portfolio.id,
                'name': portfolio.name,
                'message': 'Portfolio saved successfully!',
                'is_authenticated': True,
                'portfolios_used': current + 1,
                'portfolios_max': max_count if max_count < 999 else 'unlimited'
            })
    except Exception as e:
        logger.error(f"Save portfolio error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolios/<int:portfolio_id>', methods=['DELETE'])
def delete_portfolio(portfolio_id):
    """Delete a saved portfolio"""
    try:
        with data_manager._get_sqlite_session() as session:
            portfolio = session.query(SavedPortfolio).filter_by(id=portfolio_id).first()
            if not portfolio:
                return jsonify({'error': 'Portfolio not found'}), 404
            
            session.delete(portfolio)
            session.commit()
            return jsonify({'message': 'Portfolio deleted successfully'})
    except Exception as e:
        logger.error(f"Delete portfolio error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/portfolios/export-csv', methods=['POST'])
@optional_auth
def export_portfolio_csv():
    """Export current portfolio configuration as CSV (Premium+ feature)."""
    from webapp.user_models import get_user_by_clerk_id
    
    # Check feature access
    user = None
    if g.user_id:
        try:
            with data_manager._get_session() as session:
                user = get_user_by_clerk_id(session, g.user_id)
        except:
            pass
    
    if not can_access_feature(user, 'csv_import_export'):
        tier = get_user_tier(user)
        return jsonify({
            'error': 'feature_not_allowed',
            'message': 'CSV export requires Premium or Pro subscription',
            'feature': 'csv_import_export',
            'current_tier': tier,
            'upgrade_required': True
        }), 403
    
    try:
        data = request.json
        tickers = data.get('tickers', [])
        weights = data.get('weights', {})
        constraints = data.get('constraints', {}).get('assets', {})
        
        if not tickers:
            return jsonify({'error': 'No tickers provided'}), 400
        
        lines = ['ticker,weight_pct,min_pct,max_pct']
        
        for ticker in tickers:
            weight = weights.get(ticker, 0) * 100
            asset_constraints = constraints.get(ticker, {})
            min_pct = asset_constraints.get('min', 0) * 100 if asset_constraints else ''
            max_pct = asset_constraints.get('max', 1) * 100 if asset_constraints else ''
            
            min_str = '' if min_pct == 0 or min_pct == '' else f'{min_pct:.1f}'
            max_str = '' if max_pct == 100 or max_pct == '' else f'{max_pct:.1f}'
            
            lines.append(f'{ticker},{weight:.1f},{min_str},{max_str}')
        
        csv_content = '\n'.join(lines)
        
        return jsonify({
            'csv': csv_content,
            'filename': f'portfolio_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        })
        
    except Exception as e:
        logger.error(f"CSV export error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/portfolios/import-csv', methods=['POST'])
@optional_auth
def import_portfolio_csv():
    """Import portfolio configuration from CSV (Premium+ feature)."""
    from webapp.user_models import get_user_by_clerk_id
    
    # Check feature access
    user = None
    if g.user_id:
        try:
            with data_manager._get_session() as session:
                user = get_user_by_clerk_id(session, g.user_id)
        except:
            pass
    
    if not can_access_feature(user, 'csv_import_export'):
        tier = get_user_tier(user)
        return jsonify({
            'error': 'feature_not_allowed',
            'message': 'CSV import requires Premium or Pro subscription',
            'feature': 'csv_import_export',
            'current_tier': tier,
            'upgrade_required': True
        }), 403
    
    try:
        data = request.json
        csv_content = data.get('csv', '')
        
        if not csv_content:
            return jsonify({'error': 'No CSV content provided'}), 400
        
        lines = csv_content.strip().split('\n')
        
        start_idx = 1 if lines[0].lower().startswith('ticker') else 0
        
        tickers = []
        weights = {}
        constraints = {'assets': {}}
        errors = []
        
        for i, line in enumerate(lines[start_idx:], start=start_idx + 1):
            if not line.strip():
                continue
                
            parts = [p.strip() for p in line.split(',')]
            
            if len(parts) < 2:
                errors.append(f'Line {i}: Need at least ticker and weight')
                continue
            
            ticker = parts[0].upper()
            if '.' not in ticker:
                ticker = f'{ticker}.US'
            
            try:
                weight_pct = float(parts[1]) if parts[1] else 0
            except ValueError:
                errors.append(f'Line {i}: Invalid weight "{parts[1]}"')
                continue
            
            tickers.append(ticker)
            weights[ticker] = weight_pct / 100.0
            
            min_pct = None
            max_pct = None
            
            if len(parts) > 2 and parts[2]:
                try:
                    min_pct = float(parts[2]) / 100.0
                except ValueError:
                    pass
                    
            if len(parts) > 3 and parts[3]:
                try:
                    max_pct = float(parts[3]) / 100.0
                except ValueError:
                    pass
            
            if min_pct is not None or max_pct is not None:
                constraints['assets'][ticker] = {
                    'min': min_pct if min_pct is not None else 0,
                    'max': max_pct if max_pct is not None else 1
                }
        
        # Validate tickers exist in database
        valid_tickers = []
        invalid_tickers = []
        
        if tickers:
            coverage = data_manager.get_ticker_coverage(tickers)
            for t in tickers:
                if t in coverage:
                    valid_tickers.append(t)
                else:
                    invalid_tickers.append(t)
        
        return jsonify({
            'tickers': valid_tickers,
            'weights': {t: weights[t] for t in valid_tickers},
            'constraints': {'assets': {t: constraints['assets'].get(t, {}) for t in valid_tickers if t in constraints['assets']}},
            'invalid_tickers': invalid_tickers,
            'errors': errors,
            'message': f'Imported {len(valid_tickers)} valid tickers' + (f', {len(invalid_tickers)} not found' if invalid_tickers else '')
        })
        
    except Exception as e:
        logger.error(f"CSV import error: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# RANKINGS API (Public Leaderboard)
# ============================================================================

@app.route('/api/rankings')
@optional_auth
def get_rankings():
    """
    Get public portfolio rankings.
    
    Query params:
        sort_by: return, sharpe, sortino, health_score, volatility (default: sharpe)
        order: desc, asc (default: desc)
        limit: 1-100 (default: 50)
    """
    from webapp.user_models import UserPortfolio, User, get_user_by_clerk_id
    
    sort_by = request.args.get('sort_by', 'sharpe')
    order = request.args.get('order', 'desc')
    limit = min(int(request.args.get('limit', 50)), 100)
    
    # Map sort_by to column
    sort_columns = {
        'return': UserPortfolio.cached_return,
        'volatility': UserPortfolio.cached_volatility,
        'sharpe': UserPortfolio.cached_sharpe,
        'sortino': UserPortfolio.cached_sortino,
        'max_drawdown': UserPortfolio.cached_max_drawdown,
        'health_score': UserPortfolio.cached_health_score,
        'hhi': UserPortfolio.cached_hhi,
        'diversification_ratio': UserPortfolio.cached_div_ratio
    }
    
    sort_col = sort_columns.get(sort_by, UserPortfolio.cached_sharpe)
    
    # Check if requester can view allocations (Pro only)
    show_allocations = False
    if g.user_id:
        try:
            with data_manager._get_session() as session:
                user = get_user_by_clerk_id(session, g.user_id)
                if user and can_access_feature(user, 'view_others_allocations'):
                    show_allocations = True
        except:
            pass
    
    try:
        with data_manager._get_session() as session:
            query = session.query(UserPortfolio).join(User).filter(
                UserPortfolio.is_public == True,
                UserPortfolio.cached_sharpe.isnot(None)  # Must have cached metrics
            )
            
            if order == 'asc':
                query = query.order_by(sort_col.asc())
            else:
                query = query.order_by(sort_col.desc())
            
            portfolios = query.limit(limit).all()
            
            results = []
            for i, portfolio in enumerate(portfolios, 1):
                results.append(portfolio.to_ranking_dict(
                    rank=i, 
                    show_allocations=show_allocations
                ))
            
            return jsonify({
                'rankings': results,
                'sort_by': sort_by,
                'order': order,
                'count': len(results),
                'can_view_allocations': show_allocations
            })
            
    except Exception as e:
        logger.error(f"Rankings error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/portfolios')
@require_auth
def get_user_portfolios():
    """Get all portfolios for the authenticated user"""
    from webapp.user_models import get_user_by_clerk_id, UserPortfolio
    
    try:
        with data_manager._get_session() as session:
            user = get_user_by_clerk_id(session, g.user_id)
            
            if not user:
                return jsonify({'portfolios': []})
            
            portfolios = session.query(UserPortfolio).filter_by(
                user_id=user.id
            ).order_by(UserPortfolio.updated_at.desc()).all()
            
            # Get tier info for limits
            tier_config = get_tier_config(get_user_tier(user))
            
            return jsonify({
                'portfolios': [p.to_dict(include_allocations=True) for p in portfolios],
                'count': len(portfolios),
                'max_portfolios': tier_config['max_portfolios']
            })
            
    except Exception as e:
        logger.error(f"Get user portfolios error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/portfolios/<int:portfolio_id>', methods=['PUT'])
@require_auth
def update_user_portfolio(portfolio_id):
    """Update a user's portfolio"""
    from webapp.user_models import get_user_by_clerk_id, UserPortfolio
    
    data = request.json
    
    try:
        with data_manager._get_session() as session:
            user = get_user_by_clerk_id(session, g.user_id)
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            portfolio = session.query(UserPortfolio).filter_by(
                id=portfolio_id, 
                user_id=user.id
            ).first()
            
            if not portfolio:
                return jsonify({'error': 'Portfolio not found'}), 404
            
            # Update allowed fields
            if 'name' in data:
                portfolio.name = data['name']
            if 'description' in data:
                portfolio.description = data['description']
            if 'tickers' in data:
                portfolio.tickers = data['tickers']
            if 'weights' in data:
                portfolio.weights = data['weights']
            if 'constraints' in data:
                portfolio.constraints = data['constraints']
            if 'is_public' in data:
                portfolio.is_public = data['is_public']
            if 'show_allocations' in data:
                portfolio.show_allocations = data['show_allocations']
            
            # Clear cached metrics (will be recalculated)
            portfolio.metrics_updated_at = None
            
            session.commit()
            
            return jsonify({
                'message': 'Portfolio updated',
                'portfolio': portfolio.to_dict(include_allocations=True)
            })
            
    except Exception as e:
        logger.error(f"Update portfolio error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/user/portfolios/<int:portfolio_id>', methods=['DELETE'])
@require_auth
def delete_user_portfolio(portfolio_id):
    """Delete a user's portfolio"""
    from webapp.user_models import get_user_by_clerk_id, UserPortfolio
    
    try:
        with data_manager._get_session() as session:
            user = get_user_by_clerk_id(session, g.user_id)
            
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            portfolio = session.query(UserPortfolio).filter_by(
                id=portfolio_id, 
                user_id=user.id
            ).first()
            
            if not portfolio:
                return jsonify({'error': 'Portfolio not found'}), 404
            
            session.delete(portfolio)
            session.commit()
            
            return jsonify({'message': 'Portfolio deleted'})
            
    except Exception as e:
        logger.error(f"Delete portfolio error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/compare-portfolios', methods=['POST'])
def compare_portfolios():
    """Compare multiple saved portfolios and/or benchmarks"""
    data = request.json
    portfolio_ids = data.get('portfolio_ids', [])
    start_date = data.get('start_date', '2018-01-01')
    end_date = data.get('end_date')
    
    if not portfolio_ids:
        return jsonify({'error': 'No portfolios selected'}), 400
    
    try:
        results = []
        
        for pid in portfolio_ids:
            # Handle SPY benchmark
            if pid == 'SPY.US':
                df = data_manager.get_price_history(['SPY.US'], start_date=start_date, end_date=end_date)
                if not df.empty:
                    optimizer = PortfolioOptimizer(df)
                    weights = np.array([1.0])
                    stats = optimizer.calculate_portfolio_stats(weights)
                    stats['name'] = 'S&P 500 (SPY)'
                    results.append(stats)
                continue
            
            # Handle saved portfolios
            with data_manager._get_sqlite_session() as session:
                portfolio = session.query(SavedPortfolio).filter_by(id=int(pid)).first()
                if not portfolio:
                    continue
                
                tickers = json.loads(portfolio.tickers)
                weights_dict = json.loads(portfolio.weights)
                
                df = data_manager.get_price_history(tickers, start_date=start_date, end_date=end_date)
                if df.empty:
                    continue
                
                optimizer = PortfolioOptimizer(df)
                weights_array = np.array([weights_dict.get(t, 0) for t in tickers])
                
                if np.sum(weights_array) > 0:
                    weights_array /= np.sum(weights_array)
                    stats = optimizer.calculate_portfolio_stats(weights_array)
                    stats['name'] = portfolio.name
                    results.append(stats)
        
        return jsonify({'portfolios': results})
        
    except Exception as e:
        logger.error(f"Portfolio comparison error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ============================================================================
# 5. ENTRY POINT
# ============================================================================
if __name__ == '__main__':
    print("="*60)
    print("🚀 PORTFOLIO VISUALIZER V6 RUNNING")
    print("   URL: http://127.0.0.1:5000")
    print("="*60)
    app.run(debug=True, port=5000)
