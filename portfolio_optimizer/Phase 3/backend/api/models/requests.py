"""Request Models"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict
from datetime import date
from enum import Enum


class OptimizationMethod(str, Enum):
    MAX_SHARPE = "max_sharpe"
    MIN_VOLATILITY = "min_volatility"
    RISK_PARITY = "risk_parity"
    HRP = "hrp"
    BLACK_LITTERMAN = "black_litterman"
    EQUAL_WEIGHT = "equal_weight"


class ReturnFrequency(str, Enum):
    DAILY = "D"
    WEEKLY = "W"
    MONTHLY = "M"


class OptimizeRequest(BaseModel):
    symbols: List[str] = Field(..., min_items=2, max_items=50)
    start_date: date
    end_date: date
    method: OptimizationMethod = OptimizationMethod.MAX_SHARPE
    risk_free_rate: float = Field(default=0.02, ge=0, le=0.2)
    frequency: ReturnFrequency = ReturnFrequency.MONTHLY
    
    @validator('symbols')
    def validate_symbols(cls, v):
        if len(v) != len(set(v)):
            raise ValueError('Duplicate symbols not allowed')
        return v
    
    @validator('end_date')
    def validate_dates(cls, v, values):
        if 'start_date' in values and v <= values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class EfficientFrontierRequest(BaseModel):
    symbols: List[str] = Field(..., min_items=2, max_items=50)
    start_date: date
    end_date: date
    n_points: int = Field(default=50, ge=10, le=200)
    risk_free_rate: float = Field(default=0.02, ge=0, le=0.2)
    frequency: ReturnFrequency = ReturnFrequency.MONTHLY


class RiskMetricsRequest(BaseModel):
    symbol: str
    period: str = Field(default="1y", pattern="^(1y|3y|5y|10y|all)$")


class PortfolioPerformanceRequest(BaseModel):
    symbols: List[str] = Field(..., min_items=1, max_items=50)
    weights: List[float] = Field(..., min_items=1, max_items=50)
    start_date: date
    end_date: date
    frequency: ReturnFrequency = ReturnFrequency.MONTHLY
    
    @validator('weights')
    def validate_weights(cls, v, values):
        if 'symbols' in values and len(v) != len(values['symbols']):
            raise ValueError('Number of weights must match number of symbols')
        if abs(sum(v) - 1.0) > 0.01:
            raise ValueError('Weights must sum to 1.0')
        if any(w < 0 for w in v):
            raise ValueError('Weights must be non-negative')
        return v
