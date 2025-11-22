"""Optimization Routes"""

import sys
import numpy as np
from pathlib import Path
from fastapi import APIRouter, HTTPException

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.services import PortfolioDataService, EnhancedPortfolioOptimizer
from backend.services.optimizer import create_optimizer
from backend.services.risk_calculator import create_risk_calculator
from backend.api.models.requests import (
    OptimizeRequest,
    EfficientFrontierRequest,
    RiskMetricsRequest,
    PortfolioPerformanceRequest,
    OptimizationMethod
)
from backend.api.models.responses import (
    OptimizationResponse,
    PortfolioWeight,
    PerformanceMetrics,
    EfficientFrontierResponse,
    FrontierPoint,
    RiskMetrics as RiskMetricsResponse
)

router = APIRouter(prefix="/optimize", tags=["optimization"])


@router.post("/", response_model=OptimizationResponse)
async def optimize_portfolio(request: OptimizeRequest):
    """Optimize a portfolio using specified method"""
    try:
        # Create optimizer
        optimizer = create_optimizer(
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date,
            risk_free_rate=request.risk_free_rate,
            frequency=request.frequency.value
        )
        
        if optimizer is None:
            raise HTTPException(
                status_code=400,
                detail="Could not create optimizer. Check symbols and date range."
            )
        
        # Run optimization
        weights = None
        if request.method == OptimizationMethod.MAX_SHARPE:
            weights = optimizer.max_sharpe_ratio()
        elif request.method == OptimizationMethod.MIN_VOLATILITY:
            weights = optimizer.min_volatility()
        elif request.method == OptimizationMethod.RISK_PARITY:
            weights = optimizer.risk_parity_optimization()
        elif request.method == OptimizationMethod.HRP:
            weights = optimizer.hierarchical_risk_parity()
        elif request.method == OptimizationMethod.EQUAL_WEIGHT:
            weights = np.array([1.0 / len(request.symbols)] * len(request.symbols))
        else:
            raise HTTPException(status_code=400, detail="Unsupported optimization method")
        
        if weights is None:
            raise HTTPException(
                status_code=400,
                detail="Optimization failed. Try different method or check data quality."
            )
        
        # Get performance metrics
        perf = optimizer.portfolio_performance(weights)
        
        # Build response
        portfolio_weights = [
            PortfolioWeight(symbol=optimizer.symbols[i], weight=float(weights[i]))
            for i in range(len(weights))
        ]
        
        return OptimizationResponse(
            method=request.method.value,
            weights=portfolio_weights,
            performance=PerformanceMetrics(
                expected_return=perf['return'],
                volatility=perf['volatility'],
                sharpe_ratio=perf['sharpe'],
                sortino_ratio=perf['sortino']
            ),
            start_date=request.start_date,
            end_date=request.end_date
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/efficient-frontier", response_model=EfficientFrontierResponse)
async def calculate_efficient_frontier(request: EfficientFrontierRequest):
    """Calculate efficient frontier"""
    try:
        # Create optimizer
        optimizer = create_optimizer(
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date,
            risk_free_rate=request.risk_free_rate,
            frequency=request.frequency.value
        )
        
        if optimizer is None:
            raise HTTPException(
                status_code=400,
                detail="Could not create optimizer"
            )
        
        # Calculate frontier
        frontier_df = optimizer.efficient_frontier(n_points=request.n_points)
        
        if frontier_df is None or frontier_df.empty:
            raise HTTPException(
                status_code=400,
                detail="Could not calculate efficient frontier"
            )
        
        # Build response
        points = []
        for _, row in frontier_df.iterrows():
            ret = row['return']
            vol = row['volatility']
            sharpe = (ret - request.risk_free_rate) / vol if vol > 0 else 0
            
            points.append(FrontierPoint(
                expected_return=float(ret),
                volatility=float(vol),
                sharpe_ratio=float(sharpe)
            ))
        
        # Find optimal Sharpe and min volatility points
        optimal_idx = max(range(len(points)), key=lambda i: points[i].sharpe_ratio)
        min_vol_idx = min(range(len(points)), key=lambda i: points[i].volatility)
        
        return EfficientFrontierResponse(
            points=points,
            optimal_sharpe=points[optimal_idx],
            min_volatility=points[min_vol_idx]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/performance", response_model=PerformanceMetrics)
async def calculate_performance(request: PortfolioPerformanceRequest):
    """Calculate performance metrics for a given portfolio"""
    try:
        # Create optimizer
        optimizer = create_optimizer(
            symbols=request.symbols,
            start_date=request.start_date,
            end_date=request.end_date,
            frequency=request.frequency.value
        )
        
        if optimizer is None:
            raise HTTPException(
                status_code=400,
                detail="Could not create optimizer"
            )
        
        # Calculate performance
        weights = np.array(request.weights)
        perf = optimizer.portfolio_performance(weights)
        
        return PerformanceMetrics(
            expected_return=perf['return'],
            volatility=perf['volatility'],
            sharpe_ratio=perf['sharpe'],
            sortino_ratio=perf['sortino']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/risk-metrics/{symbol}", response_model=RiskMetricsResponse)
async def get_risk_metrics(symbol: str, period: str = "1y"):
    """Get risk metrics for a symbol"""
    try:
        calculator = create_risk_calculator()
        
        # Parse period
        period_map = {
            "1y": 1,
            "3y": 3,
            "5y": 5,
            "10y": 10,
            "all": None
        }
        
        years = period_map.get(period)
        
        metrics = calculator.calculate_all_metrics(symbol, years, period)
        
        if metrics is None:
            raise HTTPException(
                status_code=404,
                detail=f"Could not calculate metrics for {symbol}"
            )
        
        return RiskMetricsResponse(**metrics)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
