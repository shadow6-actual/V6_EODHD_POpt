"""
Portfolio Data Service
Provides data processing and preparation for portfolio optimization
"""

import sys
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from models_v6 import Asset, AssetPrice, get_session
import config_v6
from backend.database import (
    get_db_session,
    get_price_data,
    get_multiple_asset_prices,
    get_returns_dataframe,
    validate_symbols_exist
)

logger = logging.getLogger(__name__)


class PortfolioDataService:
    """Service for fetching and processing portfolio data"""
    
    def __init__(self, engine=None):
        """
        Initialize data service
        
        Args:
            engine: Optional database engine (creates new if None)
        """
        self.engine = engine or config_v6.get_postgres_engine()
    
    def get_asset_returns(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date,
        frequency: str = 'M'
    ) -> pd.DataFrame:
        """
        Fetch returns data for multiple assets
        
        Args:
            symbols: List of asset symbols
            start_date: Start date for analysis
            end_date: End date for analysis
            frequency: 'D' (daily), 'W' (weekly), or 'M' (monthly)
            
        Returns:
            DataFrame with returns (rows=dates, columns=symbols)
            
        Example:
            >>> service = PortfolioDataService()
            >>> returns = service.get_asset_returns(
            ...     ['AAPL.US', 'MSFT.US'],
            ...     start_date=datetime(2023, 1, 1).date(),
            ...     end_date=datetime.now().date(),
            ...     frequency='M'
            ... )
        """
        try:
            # Validate symbols exist
            validation = validate_symbols_exist(symbols)
            valid_symbols = [s for s, exists in validation.items() if exists]
            invalid_symbols = [s for s, exists in validation.items() if not exists]
            
            if invalid_symbols:
                logger.warning(f"Invalid symbols (will be excluded): {invalid_symbols}")
            
            if not valid_symbols:
                logger.error("No valid symbols found")
                return pd.DataFrame()
            
            # Get returns dataframe
            returns_df = get_returns_dataframe(
                valid_symbols,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency
            )
            
            if returns_df.empty:
                logger.warning("No returns data retrieved")
                return pd.DataFrame()
            
            # Check for minimum data requirements
            min_periods = {
                'D': 20,   # At least 20 trading days
                'W': 12,   # At least 12 weeks
                'M': 12    # At least 12 months
            }
            
            required_periods = min_periods.get(frequency, 12)
            
            if len(returns_df) < required_periods:
                logger.warning(
                    f"Insufficient data: {len(returns_df)} periods "
                    f"(minimum {required_periods} required for {frequency} frequency)"
                )
            
            return returns_df
            
        except Exception as e:
            logger.error(f"Failed to get asset returns: {e}")
            return pd.DataFrame()
    
    def get_price_dataframes(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date
    ) -> Dict[str, pd.DataFrame]:
        """
        Get price data for multiple symbols as dictionary of DataFrames
        
        Args:
            symbols: List of asset symbols
            start_date: Start date
            end_date: End date
            
        Returns:
            Dictionary mapping symbol to DataFrame
        """
        return get_multiple_asset_prices(symbols, start_date, end_date)
    
    def calculate_returns_statistics(
        self,
        returns_df: pd.DataFrame
    ) -> Dict[str, pd.Series]:
        """
        Calculate comprehensive return statistics
        
        Args:
            returns_df: DataFrame of returns (rows=dates, columns=assets)
            
        Returns:
            Dictionary with statistics:
            - mean_returns: Mean return for each asset
            - std_returns: Standard deviation for each asset
            - min_returns: Minimum return for each asset
            - max_returns: Maximum return for each asset
            - skewness: Skewness for each asset
            - kurtosis: Kurtosis for each asset
        """
        if returns_df.empty:
            return {}
        
        try:
            stats = {
                'mean_returns': returns_df.mean(),
                'std_returns': returns_df.std(),
                'min_returns': returns_df.min(),
                'max_returns': returns_df.max(),
                'skewness': returns_df.skew(),
                'kurtosis': returns_df.kurtosis()
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to calculate return statistics: {e}")
            return {}
    
    def calculate_covariance_matrix(
        self,
        returns_df: pd.DataFrame,
        annualize: bool = True,
        periods_per_year: int = 12
    ) -> pd.DataFrame:
        """
        Calculate covariance matrix from returns
        
        Args:
            returns_df: DataFrame of returns
            annualize: If True, annualize the covariance
            periods_per_year: Number of periods per year (12 for monthly, 252 for daily)
            
        Returns:
            Covariance matrix as DataFrame
        """
        if returns_df.empty:
            return pd.DataFrame()
        
        try:
            cov_matrix = returns_df.cov()
            
            if annualize:
                cov_matrix = cov_matrix * periods_per_year
            
            return cov_matrix
            
        except Exception as e:
            logger.error(f"Failed to calculate covariance matrix: {e}")
            return pd.DataFrame()
    
    def calculate_correlation_matrix(
        self,
        returns_df: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Calculate correlation matrix from returns
        
        Args:
            returns_df: DataFrame of returns
            
        Returns:
            Correlation matrix as DataFrame
        """
        if returns_df.empty:
            return pd.DataFrame()
        
        try:
            return returns_df.corr()
        except Exception as e:
            logger.error(f"Failed to calculate correlation matrix: {e}")
            return pd.DataFrame()
    
    def validate_portfolio_data(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date
    ) -> Dict:
        """
        Validate that sufficient data exists for portfolio optimization
        
        Args:
            symbols: List of asset symbols
            start_date: Start date
            end_date: End date
            
        Returns:
            Dictionary with validation results:
            - valid: Boolean indicating if data is sufficient
            - valid_symbols: List of symbols with sufficient data
            - invalid_symbols: List of symbols with insufficient data
            - issues: List of issue descriptions
        """
        issues = []
        valid_symbols = []
        invalid_symbols = []
        
        # Check symbol existence
        validation = validate_symbols_exist(symbols)
        
        for symbol in symbols:
            if not validation.get(symbol, False):
                invalid_symbols.append(symbol)
                issues.append(f"{symbol}: Symbol not found in database")
                continue
            
            # Get price data
            prices = get_price_data(symbol, start_date, end_date)
            
            if prices.empty:
                invalid_symbols.append(symbol)
                issues.append(f"{symbol}: No price data available")
                continue
            
            # Check minimum data points
            if len(prices) < 12:  # At least 12 data points
                invalid_symbols.append(symbol)
                issues.append(f"{symbol}: Insufficient data ({len(prices)} points)")
                continue
            
            valid_symbols.append(symbol)
        
        result = {
            'valid': len(valid_symbols) >= 2,  # Need at least 2 assets
            'valid_symbols': valid_symbols,
            'invalid_symbols': invalid_symbols,
            'issues': issues,
            'total_symbols': len(symbols),
            'valid_count': len(valid_symbols),
            'invalid_count': len(invalid_symbols)
        }
        
        if len(valid_symbols) < 2:
            issues.append("Portfolio optimization requires at least 2 valid assets")
        
        return result
    
    def prepare_optimization_data(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date,
        frequency: str = 'M'
    ) -> Dict:
        """
        Prepare all data needed for portfolio optimization
        
        Args:
            symbols: List of asset symbols
            start_date: Start date
            end_date: End date
            frequency: Return frequency ('D', 'W', or 'M')
            
        Returns:
            Dictionary with:
            - returns: Returns DataFrame
            - mean_returns: Mean returns (annualized)
            - cov_matrix: Covariance matrix (annualized)
            - symbols: List of valid symbols (may be subset of input)
            - valid: Boolean indicating if data is sufficient
        """
        # Validate data
        validation = self.validate_portfolio_data(symbols, start_date, end_date)
        
        if not validation['valid']:
            logger.error("Portfolio data validation failed")
            logger.error(f"Issues: {validation['issues']}")
            return {
                'valid': False,
                'validation': validation
            }
        
        # Use only valid symbols
        valid_symbols = validation['valid_symbols']
        
        # Get returns
        returns_df = self.get_asset_returns(
            valid_symbols,
            start_date,
            end_date,
            frequency
        )
        
        if returns_df.empty:
            return {
                'valid': False,
                'error': 'Could not calculate returns'
            }
        
        # Determine periods per year
        periods_per_year = {
            'D': 252,  # Trading days
            'W': 52,   # Weeks
            'M': 12    # Months
        }.get(frequency, 12)
        
        # Calculate statistics
        mean_returns = returns_df.mean() * periods_per_year
        cov_matrix = returns_df.cov() * periods_per_year
        
        return {
            'valid': True,
            'returns': returns_df,
            'mean_returns': mean_returns,
            'cov_matrix': cov_matrix,
            'symbols': list(returns_df.columns),
            'start_date': start_date,
            'end_date': end_date,
            'frequency': frequency,
            'periods_per_year': periods_per_year,
            'validation': validation
        }


def get_portfolio_data_service(engine=None) -> PortfolioDataService:
    """
    Factory function to create PortfolioDataService
    
    Args:
        engine: Optional database engine
        
    Returns:
        PortfolioDataService instance
    """
    return PortfolioDataService(engine=engine)
