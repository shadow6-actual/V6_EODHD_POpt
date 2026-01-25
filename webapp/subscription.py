# webapp/subscription.py
# PURPOSE: Subscription tier management and feature gating
# Defines what each tier can access and provides decorators for enforcement

from datetime import datetime, timedelta
from functools import wraps
from flask import g, jsonify
import logging

logger = logging.getLogger("Subscription")

# =============================================================================
# TIER DEFINITIONS
# =============================================================================

TIERS = {
    'free': {
        'name': 'Free',
        'price_monthly': 0,
        'max_assets': 5,
        'max_portfolios': 3,  # Requires login
        'features': {
            'basic_optimization': True,      # Max Sharpe, Min Vol, Equal Weight, Risk Parity
            'advanced_optimization': False,  # CVaR, Kelly, Omega, Sortino, Tracking Error, Min Drawdown
            'robust_optimization': False,    # Monte Carlo resampling
            'diversification_analytics': False,
            'health_score': False,
            'group_constraints': False,
            'csv_import_export': False,
            'view_others_allocations': False,
            'save_portfolios': True,  # But requires login
        }
    },
    'premium': {
        'name': 'Premium',
        'price_monthly': 14,  # Updated from $9 to $14
        'max_assets': 15,
        'max_portfolios': 20,
        'features': {
            'basic_optimization': True,
            'advanced_optimization': True,
            'robust_optimization': True,
            'diversification_analytics': False,  # Pro only
            'health_score': False,               # Pro only
            'group_constraints': False,          # Pro only
            'csv_import_export': True,
            'view_others_allocations': False,    # Pro only
            'save_portfolios': True,
        }
    },
    'pro': {
        'name': 'Pro',
        'price_monthly': 29,
        'max_assets': 999,  # Effectively unlimited
        'max_portfolios': 999,  # Effectively unlimited
        'features': {
            'basic_optimization': True,
            'advanced_optimization': True,
            'robust_optimization': True,
            'diversification_analytics': True,
            'health_score': True,
            'group_constraints': True,
            'csv_import_export': True,
            'view_others_allocations': True,
            'save_portfolios': True,
        }
    },
    'trial': {
        'name': 'Pro Trial',
        'price_monthly': 0,
        'max_assets': 999,
        'max_portfolios': 999,
        'trial_days': 1,
        'features': {
            'basic_optimization': True,
            'advanced_optimization': True,
            'robust_optimization': True,
            'diversification_analytics': True,
            'health_score': True,
            'group_constraints': True,
            'csv_import_export': True,
            'view_others_allocations': True,
            'save_portfolios': True,
        }
    }
}

# Trial period duration
TRIAL_PERIOD_DAYS = 1

# Map optimization methods to tiers
BASIC_OPTIMIZATION_METHODS = [
    'max_sharpe',
    'min_volatility', 
    'equal_weight',
    'risk_parity',
]

ADVANCED_OPTIMIZATION_METHODS = [
    'min_vol_target_return',    # Premium - target-based MVO
    'max_return_target_vol',    # Premium - target-based MVO
    'min_cvar',
    'min_cvar_target_return',
    'max_return_target_cvar',
    'min_tracking_error',
    'max_information_ratio',
    'max_excess_return_target_te',
    'max_kelly',
    'min_drawdown_target_return',
    'max_omega_target_return',
    'max_sortino_target_return'
]

ROBUST_OPTIMIZATION_METHODS = [
    'robust_max_sharpe',
    'robust_min_volatility',
    'robust_min_vol_target_return',
    'robust_max_return_target_vol'
]

# Grace period for expired subscriptions (days)
GRACE_PERIOD_DAYS = 7


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_user_tier(user):
    """
    Get the effective tier for a user, accounting for expiration and grace period.
    
    Args:
        user: User object or None (for anonymous users)
    
    Returns:
        str: 'free', 'premium', 'pro', or 'trial'
    """
    if not user:
        return 'free'
    
    tier = user.subscription_tier or 'free'
    
    # If free tier, no need to check expiration
    if tier == 'free':
        return 'free'
    
    # Check if subscription has expired
    if user.subscription_expires_at:
        now = datetime.utcnow()
        expires = user.subscription_expires_at
        grace_end = expires + timedelta(days=GRACE_PERIOD_DAYS)
        
        if now > grace_end:
            # Past grace period - downgrade to free
            logger.info(f"User {user.username} subscription expired past grace period")
            return 'free'
        elif now > expires:
            # In grace period - keep tier but log warning
            logger.info(f"User {user.username} in grace period, expires {grace_end}")
    
    return tier


def start_trial(session, user):
    """
    Start a 1-day Pro trial for a user.
    
    Args:
        session: SQLAlchemy session
        user: User object
    
    Returns:
        bool: True if trial started, False if user already had a trial
    """
    # Check if user already had a trial (could add a 'had_trial' flag to user model)
    if user.subscription_tier in ['premium', 'pro', 'trial']:
        return False
    
    user.subscription_tier = 'trial'
    user.subscription_expires_at = datetime.utcnow() + timedelta(days=TRIAL_PERIOD_DAYS)
    session.commit()
    
    logger.info(f"Started {TRIAL_PERIOD_DAYS}-day trial for user {user.username}")
    return True


def get_tier_config(tier_name):
    """Get the configuration for a tier"""
    return TIERS.get(tier_name, TIERS['free'])


def can_access_feature(user, feature_name):
    """
    Check if a user can access a specific feature.
    
    Args:
        user: User object or None
        feature_name: Feature key from tier config (e.g., 'advanced_optimization')
    
    Returns:
        bool: True if user can access the feature
    """
    tier = get_user_tier(user)
    tier_config = get_tier_config(tier)
    return tier_config['features'].get(feature_name, False)


def can_use_optimization_method(user, method_name):
    """
    Check if a user can use a specific optimization method.
    
    Args:
        user: User object or None
        method_name: Optimization method (e.g., 'max_sharpe', 'min_cvar')
    
    Returns:
        tuple: (bool allowed, str reason if not allowed)
    """
    tier = get_user_tier(user)
    tier_config = get_tier_config(tier)
    
    # Basic methods - always allowed
    if method_name in BASIC_OPTIMIZATION_METHODS:
        return True, None
    
    # Advanced methods - require premium+
    if method_name in ADVANCED_OPTIMIZATION_METHODS:
        if tier_config['features'].get('advanced_optimization'):
            return True, None
        return False, f"'{method_name}' requires Premium or Pro subscription"
    
    # Robust methods - require premium+
    if method_name in ROBUST_OPTIMIZATION_METHODS:
        if tier_config['features'].get('robust_optimization'):
            return True, None
        return False, f"Robust optimization requires Premium or Pro subscription"
    
    # Unknown method - allow (fail open for new methods)
    logger.warning(f"Unknown optimization method: {method_name}")
    return True, None


def get_max_assets(user):
    """Get the maximum number of assets a user can optimize"""
    tier = get_user_tier(user)
    return get_tier_config(tier)['max_assets']


def get_max_portfolios(user):
    """Get the maximum number of portfolios a user can save"""
    tier = get_user_tier(user)
    return get_tier_config(tier)['max_portfolios']


def get_user_portfolio_count(session, user):
    """Get the number of portfolios a user has saved"""
    if not user:
        return 0
    
    from webapp.user_models import UserPortfolio
    return session.query(UserPortfolio).filter_by(user_id=user.id).count()


def can_save_portfolio(session, user):
    """
    Check if a user can save another portfolio.
    
    Returns:
        tuple: (bool allowed, str reason if not allowed, int current_count, int max_count)
    """
    if not user:
        # Anonymous users use legacy saved_portfolios table (no limit for now)
        return True, None, 0, 0
    
    max_portfolios = get_max_portfolios(user)
    current_count = get_user_portfolio_count(session, user)
    
    if current_count >= max_portfolios:
        tier = get_user_tier(user)
        if tier == 'free':
            reason = f"Free tier limited to {max_portfolios} portfolios. Upgrade to Premium for more."
        elif tier == 'premium':
            reason = f"Premium tier limited to {max_portfolios} portfolios. Upgrade to Pro for unlimited."
        else:
            reason = f"Portfolio limit reached ({max_portfolios})"
        return False, reason, current_count, max_portfolios
    
    return True, None, current_count, max_portfolios


def get_user_tier_info(user):
    """
    Get complete tier information for a user (for frontend).
    
    Returns:
        dict: Tier info including name, limits, and feature flags
    """
    tier = get_user_tier(user)
    config = get_tier_config(tier)
    
    # Calculate days until expiration if applicable
    days_until_expiry = None
    in_grace_period = False
    
    if user and user.subscription_expires_at and tier != 'free':
        now = datetime.utcnow()
        expires = user.subscription_expires_at
        
        if now < expires:
            days_until_expiry = (expires - now).days
        elif now < expires + timedelta(days=GRACE_PERIOD_DAYS):
            in_grace_period = True
            days_until_expiry = -((now - expires).days)  # Negative = past expiry
    
    return {
        'tier': tier,
        'tier_name': config['name'],
        'max_assets': config['max_assets'],
        'max_portfolios': config['max_portfolios'],
        'features': config['features'],
        'days_until_expiry': days_until_expiry,
        'in_grace_period': in_grace_period,
        'basic_methods': BASIC_OPTIMIZATION_METHODS,
        'advanced_methods': ADVANCED_OPTIMIZATION_METHODS,
        'robust_methods': ROBUST_OPTIMIZATION_METHODS
    }


# =============================================================================
# FLASK DECORATORS
# =============================================================================

def require_feature(feature_name, upgrade_message=None):
    """
    Decorator to require a specific feature.
    Must be used after @require_auth or @optional_auth.
    
    Usage:
        @app.route('/api/export-csv')
        @require_auth
        @require_feature('csv_import_export')
        def export_csv():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = getattr(g, 'user_obj', None)
            
            if not can_access_feature(user, feature_name):
                tier = get_user_tier(user)
                msg = upgrade_message or f"This feature requires a higher subscription tier"
                return jsonify({
                    'error': 'subscription_required',
                    'message': msg,
                    'current_tier': tier,
                    'feature': feature_name
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_tier(min_tier):
    """
    Decorator to require a minimum subscription tier.
    
    Usage:
        @app.route('/api/pro-feature')
        @require_auth
        @require_tier('pro')
        def pro_only():
            ...
    """
    tier_order = {'free': 0, 'premium': 1, 'pro': 2}
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = getattr(g, 'user_obj', None)
            user_tier = get_user_tier(user)
            
            if tier_order.get(user_tier, 0) < tier_order.get(min_tier, 0):
                return jsonify({
                    'error': 'subscription_required',
                    'message': f"This feature requires {min_tier.title()} subscription or higher",
                    'current_tier': user_tier,
                    'required_tier': min_tier
                }), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# =============================================================================
# PRICING PAGE DATA
# =============================================================================

def get_pricing_data():
    """
    Get pricing information for the pricing page.
    """
    return {
        'trial_days': TRIAL_PERIOD_DAYS,
        'tiers': [
            {
                'id': 'free',
                'name': 'Free',
                'price': 0,
                'price_display': '$0',
                'period': 'forever',
                'description': 'Get started with portfolio optimization',
                'features': [
                    f'Up to {TIERS["free"]["max_assets"]} assets per optimization',
                    f'Save up to {TIERS["free"]["max_portfolios"]} portfolios (requires login)',
                    'Basic optimization (Max Sharpe, Min Vol, Risk Parity)',
                    'Efficient frontier visualization',
                    'Correlation matrix',
                    'Monthly returns heatmap'
                ],
                'limitations': [
                    'No advanced optimization methods',
                    'No CSV import/export',
                    'No diversification analytics'
                ],
                'cta': 'Get Started',
                'highlighted': False
            },
            {
                'id': 'premium',
                'name': 'Premium',
                'price': TIERS['premium']['price_monthly'],
                'price_display': f'${TIERS["premium"]["price_monthly"]}',
                'period': 'per month',
                'description': 'For serious individual investors',
                'features': [
                    f'Up to {TIERS["premium"]["max_assets"]} assets per optimization',
                    f'Save up to {TIERS["premium"]["max_portfolios"]} portfolios',
                    'All basic optimization methods',
                    'Advanced optimization (CVaR, Kelly, Sortino, Omega)',
                    'Tracking error optimization',
                    'Robust Monte Carlo optimization',
                    'CSV import/export'
                ],
                'limitations': [
                    'No diversification analytics',
                    'No group constraints',
                    'Cannot view others\' allocations'
                ],
                'cta': 'Start Premium',
                'highlighted': True
            },
            {
                'id': 'pro',
                'name': 'Pro',
                'price': TIERS['pro']['price_monthly'],
                'price_display': f'${TIERS["pro"]["price_monthly"]}',
                'period': 'per month',
                'description': 'Full power for professionals',
                'features': [
                    'Unlimited assets per optimization',
                    'Unlimited saved portfolios',
                    'All optimization methods',
                    'Diversification analytics & Health Score',
                    'Group constraints (by asset class)',
                    'View other users\' portfolio allocations',
                    'Priority support',
                    f'{TRIAL_PERIOD_DAYS}-day free trial'
                ],
                'limitations': [],
                'cta': 'Start Free Trial',
                'highlighted': False
            }
        ]
    }
