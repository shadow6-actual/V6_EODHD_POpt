"""Asset Routes"""

import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.database import (
    search_assets,
    get_asset_by_symbol,
    get_all_exchanges,
    get_price_data,
    get_asset_types
)
from backend.api.models.responses import (
    AssetInfo,
    AssetSearchResponse,
    PriceResponse,
    PriceData,
    ErrorResponse
)

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("/search", response_model=AssetSearchResponse)
async def search_assets_endpoint(
    q: str = Query(..., min_length=1, max_length=50),
    exchanges: Optional[List[str]] = Query(None),
    asset_types: Optional[List[str]] = Query(None),
    limit: int = Query(default=20, ge=1, le=100)
):
    """Search for assets by symbol, code, or name"""
    try:
        results = search_assets(
            query=q,
            limit=limit,
            exchanges=exchanges,
            asset_types=asset_types,
            active_only=True
        )
        
        asset_infos = [
            AssetInfo(
                symbol=asset.symbol,
                code=asset.code,
                name=asset.name,
                exchange=asset.exchange,
                asset_type=asset.asset_type,
                is_active=asset.is_active
            )
            for asset in results
        ]
        
        return AssetSearchResponse(
            results=asset_infos,
            total=len(asset_infos)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}", response_model=AssetInfo)
async def get_asset_endpoint(symbol: str):
    """Get detailed information for a specific asset"""
    try:
        asset = get_asset_by_symbol(symbol)
        
        if not asset:
            raise HTTPException(status_code=404, detail=f"Asset {symbol} not found")
        
        return AssetInfo(
            symbol=asset.symbol,
            code=asset.code,
            name=asset.name,
            exchange=asset.exchange,
            asset_type=asset.asset_type,
            is_active=asset.is_active
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}/prices", response_model=PriceResponse)
async def get_prices_endpoint(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get historical price data for an asset"""
    try:
        from datetime import datetime
        
        # Parse dates
        start = datetime.fromisoformat(start_date).date() if start_date else None
        end = datetime.fromisoformat(end_date).date() if end_date else None
        
        # Get price data
        df = get_price_data(symbol, start, end)
        
        if df.empty:
            raise HTTPException(
                status_code=404,
                detail=f"No price data found for {symbol}"
            )
        
        # Convert to response format
        prices = []
        for date_idx, row in df.iterrows():
            prices.append(PriceData(
                date=date_idx.date(),
                open=row.get('open'),
                high=row.get('high'),
                low=row.get('low'),
                close=row['close'],
                adjusted_close=row['adjusted_close'],
                volume=int(row['volume']) if row.get('volume') else None
            ))
        
        return PriceResponse(
            symbol=symbol,
            data=prices,
            count=len(prices)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/exchanges/list", response_model=List[str])
async def list_exchanges_endpoint():
    """Get list of all available exchanges"""
    try:
        exchanges = get_all_exchanges()
        return exchanges
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/types/list", response_model=List[str])
async def list_asset_types_endpoint(exchange: Optional[str] = None):
    """Get list of all asset types"""
    try:
        types = get_asset_types(exchange=exchange)
        return types
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
