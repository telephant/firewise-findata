"""
Symbol search routes
"""
from fastapi import APIRouter, Query
from typing import Optional
from schemas.stock import SymbolSearchResult, SymbolSearchResponse
from services import yfinance_service

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("", response_model=SymbolSearchResponse)
async def search_symbols(
    q: str = Query(..., min_length=1, description="Search query (ticker or company name)"),
    region: Optional[str] = Query(
        default=None,
        description="Filter by region: US, SG, HK, UK, JP, CN, AU, CA, DE, FR"
    ),
    type: Optional[str] = Query(
        default=None,
        description="Filter by type: stock, etf, crypto, index, currency, fund"
    ),
    limit: int = Query(default=10, ge=1, le=20, description="Max results (1-20)")
):
    """
    Search for stock symbols by name or ticker

    - **q**: Search term (required, min 1 character)
    - **region**: Filter by market region (US, SG, HK, UK, JP, CN, etc.)
    - **type**: Filter by asset type (stock, etf, crypto, index, currency, fund)
    - **limit**: Maximum results to return (default 10, max 20)
    """
    results = yfinance_service.search_symbols(
        query=q,
        region=region,
        quote_type=type,
        limit=limit
    )

    return SymbolSearchResponse(
        success=True,
        query=q,
        count=len(results),
        results=[SymbolSearchResult(**r) for r in results]
    )
