# webapp/user_models.py
# PURPOSE: Database models for user accounts and portfolio ownership
# Syncs with Clerk for authentication, stores local user data

from datetime import datetime
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
    Stores username and subscription info.
    """
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    clerk_user_id = Column(String(50), unique=True, nullable=False, index=True)
    username = Column(String(30), unique=True, nullable=False, index=True)
    
    # Optional profile info
    display_name = Column(String(100))
    bio = Column(Text)
    
    # Subscription (for future Stripe integration)
    subscription_tier = Column(String(20), default='free')  # free, premium, pro
    stripe_customer_id = Column(String(50))
    subscription_expires_at = Column(DateTime)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime)
    
    # Relationships
    portfolios = relationship("UserPortfolio", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(username='{self.username}', tier='{self.subscription_tier}')>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'subscription_tier': self.subscription_tier,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


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


# Helper functions for user management

def get_or_create_user(session, clerk_user_id, username):
    """
    Get existing user or create new one from Clerk data.
    
    Args:
        session: SQLAlchemy session
        clerk_user_id: Clerk's user ID
        username: Username from Clerk
    
    Returns:
        User object
    """
    user = session.query(User).filter_by(clerk_user_id=clerk_user_id).first()
    
    if not user:
        user = User(
            clerk_user_id=clerk_user_id,
            username=username
        )
        session.add(user)
        session.commit()
    else:
        # Update last login
        user.last_login_at = datetime.utcnow()
        # Update username if changed in Clerk
        if user.username != username:
            user.username = username
        session.commit()
    
    return user


def get_user_by_clerk_id(session, clerk_user_id):
    """Get user by Clerk ID"""
    return session.query(User).filter_by(clerk_user_id=clerk_user_id).first()


def get_user_by_username(session, username):
    """Get user by username"""
    return session.query(User).filter_by(username=username).first()
