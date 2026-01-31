# webapp/user_models.py
# PURPOSE: Database models for user accounts and portfolio ownership
# Syncs with Clerk for authentication, stores local user data

from datetime import datetime, timedelta
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text,
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from models_v6 import Base


class User(Base):
    """
    Local user record synced from Clerk.
    Stores username, subscription info, and tracking data.
    """
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    clerk_user_id = Column(String(50), unique=True, nullable=False, index=True)
    username = Column(String(30), unique=True, nullable=False, index=True)
    
    # Contact info (synced from Clerk)
    email = Column(String(255), index=True)
    email_verified = Column(Boolean, default=False)
    
    # Marketing preferences
    marketing_consent = Column(Boolean, default=False)
    marketing_consent_at = Column(DateTime)
    
    # Optional profile info
    display_name = Column(String(100))
    bio = Column(Text)
    
    # Acquisition tracking (captured at signup)
    referral_source = Column(String(100))      # utm_source or 'direct', 'organic'
    referral_campaign = Column(String(100))    # utm_campaign
    referral_medium = Column(String(100))      # utm_medium
    signup_ip_address = Column(String(45))     # IPv4 or IPv6
    signup_user_agent = Column(Text)
    
    # Subscription - Stripe integration
    subscription_tier = Column(String(20), default='free')  # free, premium, pro, trial
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    stripe_subscription_id = Column(String(255), nullable=True, index=True)
    subscription_status = Column(String(20), default='none')  # none, active, past_due, canceled, trialing
    subscription_expires_at = Column(DateTime, nullable=True)
    
    # Trial tracking
    trial_started_at = Column(DateTime)
    trial_used = Column(Boolean, default=False)
    
    # Engagement metrics
    first_optimization_at = Column(DateTime)
    total_optimizations = Column(Integer, default=0)
    last_active_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime)
    
    # Relationships
    portfolios = relationship("UserPortfolio", back_populates="user", cascade="all, delete-orphan")
    activity_logs = relationship("UserActivityLog", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(username='{self.username}', tier='{self.subscription_tier}')>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'display_name': self.display_name,
            'subscription_tier': self.subscription_tier,
            'subscription_status': self.subscription_status,
            'stripe_customer_id': self.stripe_customer_id,
            'stripe_subscription_id': self.stripe_subscription_id,
            'trial_used': self.trial_used,
            'total_optimizations': self.total_optimizations,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_active_at': self.last_active_at.isoformat() if self.last_active_at else None
        }
    
    def to_admin_dict(self):
        """Extended dict for admin views with all tracking data"""
        return {
            **self.to_dict(),
            'email_verified': self.email_verified,
            'marketing_consent': self.marketing_consent,
            'referral_source': self.referral_source,
            'referral_campaign': self.referral_campaign,
            'referral_medium': self.referral_medium,
            'signup_ip_address': self.signup_ip_address,
            'trial_started_at': self.trial_started_at.isoformat() if self.trial_started_at else None,
            'first_optimization_at': self.first_optimization_at.isoformat() if self.first_optimization_at else None,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None,
            'subscription_expires_at': self.subscription_expires_at.isoformat() if self.subscription_expires_at else None,
        }
    
    def get_days_inactive(self):
        """Calculate days since last activity"""
        if self.last_active_at:
            return (datetime.utcnow() - self.last_active_at).days
        elif self.created_at:
            return (datetime.utcnow() - self.created_at).days
        return 0
    
    def is_at_risk(self, inactive_threshold_days=30):
        """Check if user is at risk of churning"""
        return (
            self.subscription_tier in ['premium', 'pro'] and
            self.get_days_inactive() > inactive_threshold_days
        )
    
    def has_active_subscription(self):
        """Check if user has an active paid subscription"""
        return (
            self.subscription_tier in ['premium', 'pro'] and
            self.subscription_status == 'active' and
            self.stripe_subscription_id is not None
        )


class UserPortfolio(Base):
    """
    User-owned portfolios with cached performance metrics.
    Can be made public for ranking/leaderboard display.
    """
    __tablename__ = 'user_portfolios'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    # Portfolio definition
    name = Column(String(100), nullable=False)
    description = Column(Text)
    tickers = Column(JSONB, nullable=False)  # ["AAPL.US", "MSFT.US"]
    weights = Column(JSONB, nullable=False)  # {"AAPL.US": 0.5, "MSFT.US": 0.5}
    constraints = Column(JSONB)  # Optional constraints
    
    # Visibility settings
    is_public = Column(Boolean, default=False, index=True)  # Show in rankings?
    show_allocations = Column(Boolean, default=False)  # Show weights to others?
    
    # Cached performance metrics (updated periodically by background job)
    cached_return = Column(Float)  # Annualized return %
    cached_volatility = Column(Float)  # Annualized volatility %
    cached_sharpe = Column(Float)
    cached_sortino = Column(Float)
    cached_max_drawdown = Column(Float)
    cached_health_score = Column(Float)
    cached_hhi = Column(Float)
    cached_div_ratio = Column(Float)
    cached_enb = Column(Float)
    metrics_period_start = Column(DateTime)  # Analysis period
    metrics_period_end = Column(DateTime)
    metrics_updated_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="portfolios")
    
    __table_args__ = (
        Index('idx_public_sharpe', 'cached_sharpe', postgresql_where=(is_public == True)),
        Index('idx_public_return', 'cached_return', postgresql_where=(is_public == True)),
        Index('idx_public_health', 'cached_health_score', postgresql_where=(is_public == True)),
    )
    
    def __repr__(self):
        return f"<UserPortfolio(name='{self.name}', user_id={self.user_id}, public={self.is_public})>"
    
    def to_dict(self, include_allocations=False):
        """
        Convert to dictionary for API response.
        
        Args:
            include_allocations: If True, include tickers/weights (for owner or premium users)
        """
        data = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_public': self.is_public,
            'metrics': {
                'return': self.cached_return,
                'volatility': self.cached_volatility,
                'sharpe': self.cached_sharpe,
                'sortino': self.cached_sortino,
                'max_drawdown': self.cached_max_drawdown,
                'health_score': self.cached_health_score,
                'hhi': self.cached_hhi,
                'diversification_ratio': self.cached_div_ratio,
                'effective_num_bets': self.cached_enb
            },
            'metrics_updated_at': self.metrics_updated_at.isoformat() if self.metrics_updated_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_allocations:
            data['tickers'] = self.tickers
            data['weights'] = self.weights
            data['constraints'] = self.constraints
        else:
            data['ticker_count'] = len(self.tickers) if self.tickers else 0
        
        return data
    
    def to_ranking_dict(self, rank=None, show_allocations=False):
        """
        Convert to dictionary for ranking display.
        """
        data = {
            'rank': rank,
            'portfolio_id': self.id,
            'portfolio_name': self.name,
            'username': self.user.username if self.user else 'Anonymous',
            'metrics': {
                'return': round(self.cached_return, 2) if self.cached_return else None,
                'volatility': round(self.cached_volatility, 2) if self.cached_volatility else None,
                'sharpe': round(self.cached_sharpe, 2) if self.cached_sharpe else None,
                'sortino': round(self.cached_sortino, 2) if self.cached_sortino else None,
                'max_drawdown': round(self.cached_max_drawdown, 2) if self.cached_max_drawdown else None,
                'health_score': round(self.cached_health_score, 1) if self.cached_health_score else None
            }
        }
        
        if show_allocations and self.show_allocations:
            data['tickers'] = self.tickers
            data['weights'] = self.weights
        else:
            data['ticker_count'] = len(self.tickers) if self.tickers else 0
        
        return data


class UserActivityLog(Base):
    """
    Track user actions for analytics, engagement metrics, and churn prediction.
    """
    __tablename__ = 'user_activity_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    # Action details
    action_type = Column(String(50), nullable=False, index=True)  # login, optimization, portfolio_save, csv_export, etc.
    action_details = Column(JSONB)  # Flexible storage for action-specific data
    
    # Context
    ip_address = Column(String(45))
    user_agent = Column(Text)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = relationship("User", back_populates="activity_logs")
    
    __table_args__ = (
        Index('idx_activity_user_type', 'user_id', 'action_type'),
        Index('idx_activity_created', 'created_at'),
    )
    
    def __repr__(self):
        return f"<UserActivityLog(user_id={self.user_id}, action='{self.action_type}')>"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_or_create_user(session, clerk_user_id, username, email=None, email_verified=False, 
                       ip_address=None, user_agent=None, referral_source=None, 
                       referral_campaign=None, referral_medium=None):
    """
    Get existing user or create new one from Clerk data.
    Syncs user data and tracks acquisition info for new users.
    
    Args:
        session: SQLAlchemy session
        clerk_user_id: Clerk's user ID
        username: Username from Clerk
        email: Email from Clerk (optional, synced on each call)
        email_verified: Whether email is verified in Clerk
        ip_address: Client IP (captured for new users only)
        user_agent: Client user agent (captured for new users only)
        referral_source: UTM source parameter
        referral_campaign: UTM campaign parameter
        referral_medium: UTM medium parameter
    
    Returns:
        User object
    """
    user = session.query(User).filter_by(clerk_user_id=clerk_user_id).first()
    
    if not user:
        # New user - capture all acquisition data
        user = User(
            clerk_user_id=clerk_user_id,
            username=username,
            email=email,
            email_verified=email_verified,
            signup_ip_address=ip_address,
            signup_user_agent=user_agent[:500] if user_agent else None,
            referral_source=referral_source,
            referral_campaign=referral_campaign,
            referral_medium=referral_medium,
            last_login_at=datetime.utcnow(),
            last_active_at=datetime.utcnow()
        )
        session.add(user)
        session.commit()
    else:
        # Existing user - update login timestamp and sync mutable fields
        user.last_login_at = datetime.utcnow()
        user.last_active_at = datetime.utcnow()
        
        # Sync username if changed in Clerk
        if username and user.username != username:
            user.username = username
        
        # Sync email if changed in Clerk (always update to latest)
        if email and user.email != email:
            user.email = email
        
        # Update email verification status
        if email_verified and not user.email_verified:
            user.email_verified = True
        
        session.commit()
    
    return user


def get_user_by_clerk_id(session, clerk_user_id):
    """Get user by Clerk ID"""
    return session.query(User).filter_by(clerk_user_id=clerk_user_id).first()


def get_user_by_id(session, user_id):
    """Get user by internal database ID"""
    return session.query(User).filter_by(id=user_id).first()


def get_user_by_username(session, username):
    """Get user by username"""
    return session.query(User).filter_by(username=username).first()


def get_user_by_stripe_customer_id(session, stripe_customer_id):
    """Get user by Stripe customer ID"""
    return session.query(User).filter_by(stripe_customer_id=stripe_customer_id).first()


def log_user_activity(session, user_id, action_type, action_details=None, ip_address=None, user_agent=None):
    """
    Log a user activity for analytics.
    
    Args:
        session: SQLAlchemy session
        user_id: Internal user ID
        action_type: Type of action (login, optimization, portfolio_save, etc.)
        action_details: Optional dict of action-specific data
        ip_address: Client IP
        user_agent: Client user agent
    """
    log = UserActivityLog(
        user_id=user_id,
        action_type=action_type,
        action_details=action_details,
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else None
    )
    session.add(log)
    
    # Also update user's last_active_at
    user = session.query(User).filter_by(id=user_id).first()
    if user:
        user.last_active_at = datetime.utcnow()
    
    session.commit()
    return log


def get_inactive_paying_users(session, inactive_days=30):
    """
    Find paying users who haven't been active recently.
    Useful for identifying users who may have forgotten to unsubscribe
    or who need re-engagement outreach.
    
    Args:
        session: SQLAlchemy session
        inactive_days: Number of days of inactivity to flag
    
    Returns:
        List of User objects with inactive_days attribute added
    """
    cutoff = datetime.utcnow() - timedelta(days=inactive_days)
    
    users = session.query(User).filter(
        User.subscription_tier.in_(['premium', 'pro']),
        User.subscription_status == 'active',
        (User.last_active_at == None) | (User.last_active_at < cutoff)
    ).all()
    
    # Add computed inactive_days to each user
    for user in users:
        if user.last_active_at:
            user.inactive_days = (datetime.utcnow() - user.last_active_at).days
        else:
            user.inactive_days = (datetime.utcnow() - user.created_at).days if user.created_at else 999
    
    return sorted(users, key=lambda u: u.inactive_days, reverse=True)


def get_engagement_leaderboard(session, min_active_months=2, limit=50):
    """
    Get top engaged users ranked by engagement rate.
    
    Args:
        session: SQLAlchemy session
        min_active_months: Minimum months of activity to qualify
        limit: Maximum number of users to return
    
    Returns:
        List of users with engagement metrics
    """
    from sqlalchemy import func
    
    # Calculate engagement based on activity logs
    cutoff = datetime.utcnow() - timedelta(days=min_active_months * 30)
    
    results = session.query(
        User,
        func.count(UserActivityLog.id).label('total_actions'),
        func.count(func.distinct(func.date(UserActivityLog.created_at))).label('active_days')
    ).join(
        UserActivityLog, User.id == UserActivityLog.user_id
    ).filter(
        UserActivityLog.created_at >= cutoff
    ).group_by(
        User.id
    ).having(
        func.count(func.distinct(func.date(UserActivityLog.created_at))) >= min_active_months * 4  # ~1 visit/week
    ).order_by(
        func.count(UserActivityLog.id).desc()
    ).limit(limit).all()
    
    return [
        {
            'user': user,
            'total_actions': total_actions,
            'active_days': active_days,
            'engagement_rate': round(active_days / (min_active_months * 30) * 100, 1)
        }
        for user, total_actions, active_days in results
    ]
