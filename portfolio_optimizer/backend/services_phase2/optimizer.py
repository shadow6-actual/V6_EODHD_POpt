"""
Enhanced Portfolio Optimizer V6
Migrated to use PostgreSQL database via models_v6 and config_v6

Implements advanced optimization methods:
- Maximum Sharpe Ratio
- Minimum Volatility
- Maximum Return (with volatility constraint)
- Risk Parity (Equal Risk Contribution)
- Hierarchical Risk Parity (HRP)
- Black-Litterman
- Efficient Frontier
"""

import sys
import logging
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, date, timedelta
from scipy.optimize import minimize
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform
from typing import List, Dict, Optional, Tuple
import warnings

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from models_v6 import Asset, AssetPrice, get_session
import config_v6
from backend.services.data_service import PortfolioDataService

warnings.filterwarnings("ignore", category=RuntimeWarning)

logger = logging.getLogger(__name__)


class EnhancedPortfolioOptimizer:
    """Advanced portfolio optimization with multiple methods"""
    
    def __init__(self, returns_data: pd.DataFrame, risk_free_rate: float = 0.02):
        """
        Initialize optimizer
        
        Args:
            returns_data: DataFrame of asset returns (rows=dates, cols=assets)
            risk_free_rate: Annual risk-free rate (default 2%)
        """
        if returns_data.empty:
            raise ValueError("Returns data cannot be empty")
        
        self.returns = returns_data
        self.risk_free_rate = risk_free_rate
        self.mean_returns = returns_data.mean() * 12  # Annualized (assuming monthly)
        self.cov_matrix = returns_data.cov() * 12  # Annualized
        self.n_assets = len(returns_data.columns)
        self.symbols = list(returns_data.columns)
        
        logger.info(f"Optimizer initialized with {self.n_assets} assets")
        logger.info(f"Date range: {returns_data.index[0]} to {returns_data.index[-1]}")
        logger.info(f"Number of periods: {len(returns_data)}")
    
    # ========================================================================
    # TRADITIONAL OPTIMIZATION METHODS
    # ========================================================================
    
    def max_sharpe_ratio(self, constraints: List[Dict] = None) -> Optional[np.ndarray]:
        """
        Maximize Sharpe ratio
        
        Args:
            constraints: Optional list of constraint dictionaries
            
        Returns:
            Array of optimal weights or None if optimization fails
        """
        def neg_sharpe(weights):
            port_return = np.sum(self.mean_returns * weights)
            port_vol = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
            if port_vol == 0:
                return np.inf
            return -(port_return - self.risk_free_rate) / port_vol
        
        bounds = tuple((0, 1) for _ in range(self.n_assets))
        constraints_list = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
        
        if constraints:
            constraints_list.extend(constraints)
        
        try:
            result = minimize(
                neg_sharpe,
                x0=np.array([1/self.n_assets] * self.n_assets),
                method='SLSQP',
                bounds=bounds,
                constraints=constraints_list
            )
            
            if result.success:
                logger.info("Max Sharpe optimization successful")
                return result.x
            else:
                logger.warning(f"Max Sharpe optimization failed: {result.message}")
                return None
                
        except Exception as e:
            logger.error(f"Max Sharpe optimization error: {e}")
            return None
    
    def min_volatility(self, constraints: List[Dict] = None) -> Optional[np.ndarray]:
        """
        Minimize portfolio volatility
        
        Args:
            constraints: Optional list of constraint dictionaries
            
        Returns:
            Array of optimal weights or None if optimization fails
        """
        def portfolio_volatility(weights):
            return np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
        
        bounds = tuple((0, 1) for _ in range(self.n_assets))
        constraints_list = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
        
        if constraints:
            constraints_list.extend(constraints)
        
        try:
            result = minimize(
                portfolio_volatility,
                x0=np.array([1/self.n_assets] * self.n_assets),
                method='SLSQP',
                bounds=bounds,
                constraints=constraints_list
            )
            
            if result.success:
                logger.info("Min Volatility optimization successful")
                return result.x
            else:
                logger.warning(f"Min Volatility optimization failed: {result.message}")
                return None
                
        except Exception as e:
            logger.error(f"Min Volatility optimization error: {e}")
            return None
    
    def max_return(
        self,
        max_volatility: float,
        constraints: List[Dict] = None
    ) -> Optional[np.ndarray]:
        """
        Maximize return with volatility constraint
        
        Args:
            max_volatility: Maximum allowed portfolio volatility
            constraints: Optional list of constraint dictionaries
            
        Returns:
            Array of optimal weights or None if optimization fails
        """
        def neg_return(weights):
            return -np.sum(self.mean_returns * weights)
        
        def volatility_constraint(weights):
            vol = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
            return max_volatility - vol
        
        bounds = tuple((0, 1) for _ in range(self.n_assets))
        constraints_list = [
            {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
            {'type': 'ineq', 'fun': volatility_constraint}
        ]
        
        if constraints:
            constraints_list.extend(constraints)
        
        try:
            result = minimize(
                neg_return,
                x0=np.array([1/self.n_assets] * self.n_assets),
                method='SLSQP',
                bounds=bounds,
                constraints=constraints_list
            )
            
            if result.success:
                logger.info("Max Return optimization successful")
                return result.x
            else:
                logger.warning(f"Max Return optimization failed: {result.message}")
                return None
                
        except Exception as e:
            logger.error(f"Max Return optimization error: {e}")
            return None
    
    # ========================================================================
    # RISK PARITY OPTIMIZATION
    # ========================================================================
    
    def risk_parity_optimization(self) -> Optional[np.ndarray]:
        """
        Equal Risk Contribution portfolio
        Each asset contributes equally to portfolio risk
        
        Returns:
            Array of optimal weights or None if optimization fails
        """
        def risk_budget_objective(weights):
            # Calculate portfolio volatility
            port_vol = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
            
            # Avoid division by zero
            if port_vol == 0:
                return np.inf
            
            # Calculate marginal contribution to risk
            marginal_contrib = np.dot(self.cov_matrix, weights) / port_vol
            
            # Risk contribution of each asset
            risk_contrib = weights * marginal_contrib
            
            # Target risk contribution (equal for all)
            target_risk = port_vol / self.n_assets
            
            # Minimize sum of squared deviations from target
            return np.sum((risk_contrib - target_risk) ** 2)
        
        bounds = tuple((0, 1) for _ in range(self.n_assets))
        constraints = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
        
        try:
            result = minimize(
                risk_budget_objective,
                x0=np.array([1/self.n_assets] * self.n_assets),
                method='SLSQP',
                bounds=bounds,
                constraints=constraints
            )
            
            if result.success:
                logger.info("Risk Parity optimization successful")
                return result.x
            else:
                logger.warning(f"Risk Parity optimization failed: {result.message}")
                return None
                
        except Exception as e:
            logger.error(f"Risk Parity optimization error: {e}")
            return None
    
    # ========================================================================
    # HIERARCHICAL RISK PARITY (HRP)
    # ========================================================================
    
    def hierarchical_risk_parity(self) -> Optional[np.ndarray]:
        """
        Hierarchical Risk Parity (Marcos López de Prado)
        Uses hierarchical clustering to build portfolio
        
        Returns:
            Array of optimal weights or None if optimization fails
        """
        try:
            # Step 1: Calculate correlation matrix
            corr_matrix = self.returns.corr()
            
            # Convert correlation to distance matrix
            dist_matrix = np.sqrt((1 - corr_matrix) / 2)
            
            # Step 2: Hierarchical clustering
            linkage_matrix = linkage(squareform(dist_matrix), method='single')
            
            # Step 3: Quasi-diagonalization
            sorted_indices = self._quasi_diag(linkage_matrix)
            
            # Step 4: Recursive bisection
            weights = self._recursive_bisection(sorted_indices)
            
            logger.info("Hierarchical Risk Parity optimization successful")
            return weights
            
        except Exception as e:
            logger.error(f"HRP optimization error: {e}")
            return None
    
    def _quasi_diag(self, linkage_matrix: np.ndarray) -> List[int]:
        """Reorganize matrix for quasi-diagonalization"""
        n = linkage_matrix.shape[0] + 1
        
        def _cluster_indices(node):
            if node < n:
                return [node]
            else:
                left = int(linkage_matrix[int(node - n), 0])
                right = int(linkage_matrix[int(node - n), 1])
                return _cluster_indices(left) + _cluster_indices(right)
        
        sorted_indices = _cluster_indices(2 * n - 2)
        return sorted_indices
    
    def _recursive_bisection(self, sorted_indices: List[int]) -> np.ndarray:
        """Recursively allocate weights using inverse variance"""
        weights = np.zeros(self.n_assets)
        
        def _bisect(indices, weight=1.0):
            if len(indices) == 1:
                weights[indices[0]] = weight
                return
            
            # Split cluster in half
            mid = len(indices) // 2
            left_indices = indices[:mid]
            right_indices = indices[mid:]
            
            # Calculate cluster variance
            left_var = self._cluster_variance(left_indices)
            right_var = self._cluster_variance(right_indices)
            
            # Allocate weights inversely proportional to variance
            total_var = left_var + right_var
            if total_var == 0:
                left_weight = 0.5
            else:
                left_weight = right_var / total_var
            
            right_weight = 1 - left_weight
            
            # Recursive bisection
            _bisect(left_indices, weight * left_weight)
            _bisect(right_indices, weight * right_weight)
        
        _bisect(sorted_indices)
        return weights
    
    def _cluster_variance(self, indices: List[int]) -> float:
        """Calculate variance of a cluster"""
        if len(indices) == 1:
            return self.cov_matrix.iloc[indices[0], indices[0]]
        
        cov_slice = self.cov_matrix.iloc[indices, indices]
        weights = np.array([1/len(indices)] * len(indices))
        
        variance = np.dot(weights.T, np.dot(cov_slice, weights))
        return variance
    
    # ========================================================================
    # BLACK-LITTERMAN MODEL
    # ========================================================================
    
    def black_litterman(
        self,
        market_weights: np.ndarray,
        views: Dict[int, float],
        view_confidence: float = 0.25,
        tau: float = 0.05,
        lam: float = 2.5
    ) -> Optional[np.ndarray]:
        """
        Black-Litterman model with investor views
        
        Args:
            market_weights: Current market cap weights
            views: Dictionary mapping asset index to expected return
            view_confidence: Confidence in views (0-1)
            tau: Uncertainty parameter
            lam: Risk aversion parameter
            
        Returns:
            Array of optimal weights or None if optimization fails
        """
        try:
            # Market implied equilibrium returns (reverse optimization)
            pi = lam * np.dot(self.cov_matrix, market_weights)
            
            # View matrix P and view vector Q
            n_views = len(views)
            P = np.zeros((n_views, self.n_assets))
            Q = np.zeros(n_views)
            
            for i, (asset_idx, view_return) in enumerate(views.items()):
                P[i, asset_idx] = 1
                Q[i] = view_return
            
            # Omega (uncertainty in views)
            omega = np.diag([view_confidence * tau * self.cov_matrix.iloc[i, i] 
                           for i in views.keys()])
            
            # Black-Litterman formula
            tau_sigma = tau * self.cov_matrix
            
            # Posterior covariance
            M_inv = np.linalg.inv(
                np.linalg.inv(tau_sigma) + P.T @ np.linalg.inv(omega) @ P
            )
            
            # Posterior returns
            posterior_returns = M_inv @ (
                np.linalg.inv(tau_sigma) @ pi + P.T @ np.linalg.inv(omega) @ Q
            )
            
            # Optimize with posterior returns
            def neg_utility(weights):
                port_return = np.sum(posterior_returns * weights)
                port_var = np.dot(weights.T, np.dot(self.cov_matrix, weights))
                return -(port_return - lam/2 * port_var)
            
            bounds = tuple((0, 1) for _ in range(self.n_assets))
            constraints = [{'type': 'eq', 'fun': lambda x: np.sum(x) - 1}]
            
            result = minimize(
                neg_utility,
                x0=market_weights,
                method='SLSQP',
                bounds=bounds,
                constraints=constraints
            )
            
            if result.success:
                logger.info("Black-Litterman optimization successful")
                return result.x
            else:
                logger.warning(f"Black-Litterman optimization failed: {result.message}")
                return market_weights
                
        except Exception as e:
            logger.error(f"Black-Litterman optimization error: {e}")
            return market_weights
    
    # ========================================================================
    # EFFICIENT FRONTIER
    # ========================================================================
    
    def efficient_frontier(self, n_points: int = 100) -> Optional[pd.DataFrame]:
        """
        Calculate efficient frontier
        
        Args:
            n_points: Number of points on the frontier
            
        Returns:
            DataFrame with returns, volatilities, and weights for each point
        """
        try:
            # Find min/max returns
            min_vol_weights = self.min_volatility()
            max_sharpe_weights = self.max_sharpe_ratio()
            
            if min_vol_weights is None or max_sharpe_weights is None:
                logger.error("Could not calculate efficient frontier bounds")
                return None
            
            min_return = np.sum(self.mean_returns * min_vol_weights)
            max_return = np.sum(self.mean_returns * max_sharpe_weights)
            
            target_returns = np.linspace(min_return, max_return, n_points)
            
            frontier_volatility = []
            frontier_returns = []
            frontier_weights = []
            
            for target_return in target_returns:
                def portfolio_volatility(weights):
                    return np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
                
                def return_constraint(weights):
                    return np.sum(self.mean_returns * weights) - target_return
                
                bounds = tuple((0, 1) for _ in range(self.n_assets))
                constraints = [
                    {'type': 'eq', 'fun': lambda x: np.sum(x) - 1},
                    {'type': 'eq', 'fun': return_constraint}
                ]
                
                result = minimize(
                    portfolio_volatility,
                    x0=np.array([1/self.n_assets] * self.n_assets),
                    method='SLSQP',
                    bounds=bounds,
                    constraints=constraints
                )
                
                if result.success:
                    frontier_returns.append(target_return)
                    frontier_volatility.append(result.fun)
                    frontier_weights.append(result.x)
            
            if not frontier_returns:
                logger.error("No valid frontier points found")
                return None
            
            logger.info(f"Efficient frontier calculated with {len(frontier_returns)} points")
            
            return pd.DataFrame({
                'return': frontier_returns,
                'volatility': frontier_volatility,
                'weights': frontier_weights
            })
            
        except Exception as e:
            logger.error(f"Efficient frontier calculation error: {e}")
            return None
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def portfolio_performance(self, weights: np.ndarray) -> Dict:
        """
        Calculate portfolio performance metrics
        
        Args:
            weights: Array of portfolio weights
            
        Returns:
            Dictionary with performance metrics
        """
        try:
            port_return = np.sum(self.mean_returns * weights)
            port_vol = np.sqrt(np.dot(weights.T, np.dot(self.cov_matrix, weights)))
            sharpe = (port_return - self.risk_free_rate) / port_vol if port_vol > 0 else 0
            
            # Calculate downside deviation
            portfolio_returns = self.returns @ weights
            downside_returns = portfolio_returns[portfolio_returns < 0]
            downside_vol = downside_returns.std() * np.sqrt(12) if len(downside_returns) > 0 else 0
            sortino = (port_return - self.risk_free_rate) / downside_vol if downside_vol > 0 else 0
            
            return {
                'return': float(port_return),
                'volatility': float(port_vol),
                'sharpe': float(sharpe),
                'sortino': float(sortino)
            }
            
        except Exception as e:
            logger.error(f"Performance calculation error: {e}")
            return {
                'return': 0.0,
                'volatility': 0.0,
                'sharpe': 0.0,
                'sortino': 0.0
            }
    
    def get_weights_dataframe(self, weights: np.ndarray) -> pd.DataFrame:
        """
        Convert weight array to DataFrame with symbols
        
        Args:
            weights: Array of weights
            
        Returns:
            DataFrame with symbols and weights
        """
        return pd.DataFrame({
            'symbol': self.symbols,
            'weight': weights
        }).sort_values('weight', ascending=False)


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def create_optimizer(
    symbols: List[str],
    start_date: date,
    end_date: date,
    risk_free_rate: float = 0.02,
    frequency: str = 'M',
    engine=None
) -> Optional[EnhancedPortfolioOptimizer]:
    """
    Factory function to create optimizer with data from database
    
    Args:
        symbols: List of asset symbols
        start_date: Start date for analysis
        end_date: End date for analysis
        risk_free_rate: Annual risk-free rate
        frequency: Return frequency ('D', 'W', or 'M')
        engine: Optional database engine
        
    Returns:
        EnhancedPortfolioOptimizer instance or None if data insufficient
    """
    try:
        # Create data service
        data_service = PortfolioDataService(engine=engine)
        
        # Get returns data
        returns_df = data_service.get_asset_returns(
            symbols,
            start_date,
            end_date,
            frequency
        )
        
        if returns_df.empty:
            logger.error("Could not retrieve returns data")
            return None
        
        # Create optimizer
        optimizer = EnhancedPortfolioOptimizer(returns_df, risk_free_rate)
        
        return optimizer
        
    except Exception as e:
        logger.error(f"Failed to create optimizer: {e}")
        return None
