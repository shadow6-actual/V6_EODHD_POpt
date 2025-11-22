"""Response Models"""

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import date, datetime


class AssetInfo(BaseModel):
    symbol: str
    code: str
    name: str
    exchange: str
    asset_type: str
    is_active: bool


class AssetSearchResponse(BaseModel):
    results: List[AssetInfo]
    total: int


class PriceData(BaseModel):
    date: date
    open: Optional[float]
    high: Optional[float]
    low: Optional[float]
    close: float
    adjusted_close: float
    volume: Optional[int]


class PriceResponse(BaseModel):
    symbol: str
    data: List[PriceData]
    count: int


class PortfolioWeight(BaseModel):
    symbol: str
    weight: float


class PerformanceMetrics(BaseModel):
    expected_return: float
    volatility: float
    sharpe_ratio: float
    sortino_ratio: float


class OptimizationResponse(BaseModel):
    method: str
    weights: List[PortfolioWeight]
    performance: PerformanceMetrics
    start_date: date
    end_date: date


class FrontierPoint(BaseModel):
    expected_return: float
    volatility: float
    sharpe_ratio: float


class EfficientFrontierResponse(BaseModel):
    points: List[FrontierPoint]
    optimal_sharpe: FrontierPoint
    min_volatility: FrontierPoint


class RiskMetrics(BaseModel):
    symbol: str
    period: str
    volatility: Optional[float]
    downside_deviation: Optional[float]
    max_drawdown: Optional[float]
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    calmar_ratio: Optional[float]
    var_95: Optional[float]
    cvar_95: Optional[float]
    skewness: Optional[float]
    kurtosis: Optional[float]
    last_calculated: Optional[datetime]


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    status_code: int
