"""
Risk Metrics Calculator V6
Migrated to use PostgreSQL database via models_v6 and config_v6

Pre-calculates risk metrics for assets across different time periods
"""

import sys
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from typing import List, Optional, Dict

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from models_v6 import Asset, AssetPrice, get_session
import config_v6
from backend.database import get_db_session, get_price_data

logger = logging.getLogger(__name__)


class RiskMetricsCalculator:
    """Calculate comprehensive risk metrics for assets"""
    
    def __init__(self, risk_free_rate: float = 0.02, engine=None):
        """
        Initialize calculator
        
        Args:
            risk_free_rate: Annual risk-free rate (default 2%)
            engine: Optional database engine
        """
        self.risk_free_rate = risk_free_rate
        self.engine = engine or config_v6.get_postgres_engine()
    
    @staticmethod
    def get_price_data_for_symbol(
        symbol: str,
        years_back: Optional[int] = None,
        engine=None
    ) -> pd.DataFrame:
        """
        Fetch historical price data for a symbol
        
        Args:
            symbol: Asset symbol
            years_back: Number of years to look back (None = all data)
            engine: Optional database engine
            
        Returns:
            DataFrame with price data
        """
        if years_back:
            start_date = datetime.now().date() - relativedelta(years=years_back)
        else:
            start_date = None
        
        end_date = datetime.now().date()
        
        df = get_price_data(symbol, start_date, end_date)
        
        return df
    
    @staticmethod
    def calculate_returns(df: pd.DataFrame) -> pd.Series:
        """
        Calculate monthly returns from price data
        
        Args:
            df: DataFrame with price data (must have 'adjusted_close' column)
            
        Returns:
            Series of monthly returns
        """
        if df.empty or 'adjusted_close' not in df.columns:
            return pd.Series(dtype=float)
        
        # Use adjusted close for total return calculation
        monthly_data = df['adjusted_close'].resample('M').last()
        returns = monthly_data.pct_change().dropna()
        
        return returns
    
    @staticmethod
    def calculate_volatility(returns: pd.Series, annualize: bool = True) -> float:
        """
        Calculate annualized volatility
        
        Args:
            returns: Series of returns
            annualize: If True, annualize the volatility
            
        Returns:
            Volatility value
        """
        if len(returns) < 2:
            return np.nan
        
        vol = returns.std()
        if annualize:
            vol = vol * np.sqrt(12)  # Monthly to annual
        
        return float(vol)
    
    @staticmethod
    def calculate_downside_deviation(
        returns: pd.Series,
        annualize: bool = True
    ) -> float:
        """
        Calculate downside deviation (semi-deviation)
        
        Args:
            returns: Series of returns
            annualize: If True, annualize the deviation
            
        Returns:
            Downside deviation value
        """
        if len(returns) < 2:
            return np.nan
        
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0:
            return 0.0
        
        downside_dev = downside_returns.std()
        if annualize:
            downside_dev = downside_dev * np.sqrt(12)
        
        return float(downside_dev)
    
    @staticmethod
    def calculate_max_drawdown(df: pd.DataFrame) -> float:
        """
        Calculate maximum drawdown
        
        Args:
            df: DataFrame with price data
            
        Returns:
            Maximum drawdown (as positive value)
        """
        if df.empty or 'adjusted_close' not in df.columns:
            return np.nan
        
        prices = df['adjusted_close']
        cummax = prices.cummax()
        drawdowns = (prices - cummax) / cummax
        
        max_dd = drawdowns.min()
        return float(abs(max_dd))
    
    @staticmethod
    def calculate_sharpe_ratio(
        returns: pd.Series,
        risk_free_rate: float,
        annualize: bool = True
    ) -> float:
        """
        Calculate Sharpe ratio
        
        Args:
            returns: Series of returns
            risk_free_rate: Annual risk-free rate
            annualize: If True, annualize returns and volatility
            
        Returns:
            Sharpe ratio
        """
        if len(returns) < 2:
            return np.nan
        
        mean_return = returns.mean()
        std_return = returns.std()
        
        if annualize:
            mean_return = mean_return * 12
            std_return = std_return * np.sqrt(12)
        
        if std_return == 0:
            return np.nan
        
        sharpe = (mean_return - risk_free_rate) / std_return
        return float(sharpe)
    
    @staticmethod
    def calculate_sortino_ratio(
        returns: pd.Series,
        risk_free_rate: float,
        annualize: bool = True
    ) -> float:
        """
        Calculate Sortino ratio
        
        Args:
            returns: Series of returns
            risk_free_rate: Annual risk-free rate
            annualize: If True, annualize returns and downside deviation
            
        Returns:
            Sortino ratio
        """
        if len(returns) < 2:
            return np.nan
        
        mean_return = returns.mean()
        downside_returns = returns[returns < 0]
        
        if len(downside_returns) == 0:
            return np.nan
        
        downside_std = downside_returns.std()
        
        if annualize:
            mean_return = mean_return * 12
            downside_std = downside_std * np.sqrt(12)
        
        if downside_std == 0:
            return np.nan
        
        sortino = (mean_return - risk_free_rate) / downside_std
        return float(sortino)
    
    @staticmethod
    def calculate_calmar_ratio(returns: pd.Series, max_drawdown: float) -> float:
        """
        Calculate Calmar ratio (return / max drawdown)
        
        Args:
            returns: Series of returns
            max_drawdown: Maximum drawdown value
            
        Returns:
            Calmar ratio
        """
        if max_drawdown == 0 or np.isnan(max_drawdown):
            return np.nan
        
        annual_return = returns.mean() * 12
        calmar = annual_return / max_drawdown
        
        return float(calmar)
    
    @staticmethod
    def calculate_var(returns: pd.Series, confidence: float = 0.95) -> float:
        """
        Calculate Value at Risk at given confidence level
        
        Args:
            returns: Series of returns
            confidence: Confidence level (e.g., 0.95 for 95%)
            
        Returns:
            VaR value (as positive number)
        """
        if len(returns) < 10:
            return np.nan
        
        var = np.percentile(returns, (1 - confidence) * 100)
        return float(abs(var))
    
    @staticmethod
    def calculate_cvar(returns: pd.Series, confidence: float = 0.95) -> float:
        """
        Calculate Conditional VaR (Expected Shortfall)
        
        Args:
            returns: Series of returns
            confidence: Confidence level (e.g., 0.95 for 95%)
            
        Returns:
            CVaR value (as positive number)
        """
        if len(returns) < 10:
            return np.nan
        
        var_threshold = np.percentile(returns, (1 - confidence) * 100)
        cvar = returns[returns <= var_threshold].mean()
        
        return float(abs(cvar))
    
    @staticmethod
    def calculate_skewness(returns: pd.Series) -> float:
        """
        Calculate skewness of returns distribution
        
        Args:
            returns: Series of returns
            
        Returns:
            Skewness value
        """
        if len(returns) < 3:
            return np.nan
        
        return float(returns.skew())
    
    @staticmethod
    def calculate_kurtosis(returns: pd.Series) -> float:
        """
        Calculate excess kurtosis of returns distribution
        
        Args:
            returns: Series of returns
            
        Returns:
            Kurtosis value
        """
        if len(returns) < 4:
            return np.nan
        
        return float(returns.kurtosis())
    
    def calculate_all_metrics(
        self,
        symbol: str,
        period_years: Optional[int] = None,
        period_label: str = 'all'
    ) -> Optional[Dict]:
        """
        Calculate all risk metrics for a symbol
        
        Args:
            symbol: Asset symbol
            period_years: Number of years to analyze (None = all available)
            period_label: Label for the period (e.g., '1y', '3y', 'all')
            
        Returns:
            Dictionary with all risk metrics or None if insufficient data
        """
        # Get price data
        df = self.get_price_data_for_symbol(symbol, period_years, self.engine)
        
        if df.empty or len(df) < 12:  # Need at least 12 months
            logger.warning(f"{symbol}: Insufficient data for {period_label} period")
            return None
        
        # Calculate returns
        returns = self.calculate_returns(df)
        
        if len(returns) < 2:
            logger.warning(f"{symbol}: Could not calculate returns for {period_label} period")
            return None
        
        # Calculate all metrics
        max_dd = self.calculate_max_drawdown(df)
        
        metrics = {
            'symbol': symbol,
            'period': period_label,
            'volatility': self.calculate_volatility(returns),
            'downside_deviation': self.calculate_downside_deviation(returns),
            'max_drawdown': max_dd,
            'sharpe_ratio': self.calculate_sharpe_ratio(returns, self.risk_free_rate),
            'sortino_ratio': self.calculate_sortino_ratio(returns, self.risk_free_rate),
            'calmar_ratio': self.calculate_calmar_ratio(returns, max_dd),
            'var_95': self.calculate_var(returns, 0.95),
            'cvar_95': self.calculate_cvar(returns, 0.95),
            'skewness': self.calculate_skewness(returns),
            'kurtosis': self.calculate_kurtosis(returns),
            'last_calculated': datetime.utcnow()
        }
        
        return metrics
    
    def update_metrics_for_symbol(
        self,
        symbol: str,
        periods: Optional[List[tuple]] = None
    ) -> int:
        """
        Calculate and return metrics for all periods for a symbol
        
        Args:
            symbol: Asset symbol
            periods: List of (years, label) tuples. If None, uses default periods
            
        Returns:
            Number of metric sets calculated
        """
        if periods is None:
            periods = [
                (1, '1y'),
                (3, '3y'),
                (5, '5y'),
                (10, '10y'),
                (None, 'all')
            ]
        
        metrics_calculated = 0
        all_metrics = []
        
        for years, label in periods:
            try:
                metrics = self.calculate_all_metrics(symbol, years, label)
                
                if metrics:
                    all_metrics.append(metrics)
                    metrics_calculated += 1
                    logger.debug(f"{symbol} - {label}: Metrics calculated")
                    
            except Exception as e:
                logger.error(f"Error calculating {label} metrics for {symbol}: {e}")
        
        return metrics_calculated, all_metrics
    
    def calculate_metrics_batch(
        self,
        symbols: List[str],
        periods: Optional[List[tuple]] = None
    ) -> Dict[str, List[Dict]]:
        """
        Calculate risk metrics for multiple symbols
        
        Args:
            symbols: List of asset symbols
            periods: List of (years, label) tuples
            
        Returns:
            Dictionary mapping symbol to list of metrics for each period
        """
        results = {}
        
        logger.info(f"Calculating risk metrics for {len(symbols)} symbols...")
        
        for i, symbol in enumerate(symbols, 1):
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(symbols)}")
            
            try:
                count, metrics_list = self.update_metrics_for_symbol(symbol, periods)
                if metrics_list:
                    results[symbol] = metrics_list
            except Exception as e:
                logger.error(f"Error calculating metrics for {symbol}: {e}")
        
        logger.info(f"Completed: Calculated metrics for {len(results)} symbols")
        return results


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_risk_calculator(
    risk_free_rate: float = 0.02,
    engine=None
) -> RiskMetricsCalculator:
    """
    Factory function to create RiskMetricsCalculator
    
    Args:
        risk_free_rate: Annual risk-free rate
        engine: Optional database engine
        
    Returns:
        RiskMetricsCalculator instance
    """
    return RiskMetricsCalculator(risk_free_rate=risk_free_rate, engine=engine)
