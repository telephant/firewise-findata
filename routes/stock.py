"""
Stock price routes
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor
from schemas.stock import (
    StockPrice, StockPriceRequest, StockPriceResponse,
    CompanyInfo, HistoricalPriceResponse,
    CAGRResponse, CAGRBatchRequest, CAGRBatchResponse,
    PriceAtDateResponse
)
from services import yfinance_service
import config

# Thread pool for parallel yfinance calls
executor = ThreadPoolExecutor(max_workers=10)

router = APIRouter(prefix="/stock", tags=["Stock"])


@router.get("/price/{ticker}", response_model=StockPrice)
async def get_stock_price(ticker: str):
    """
    Get current stock price for a single ticker
    """
    result = yfinance_service.get_stock_price(ticker.upper())
    if not result:
        raise HTTPException(status_code=404, detail=f"Could not fetch price for {ticker}")
    return result


@router.post("/prices", response_model=StockPriceResponse)
async def get_stock_prices(request: StockPriceRequest):
    """
    Get current stock prices for multiple tickers (batch)
    """
    if len(request.tickers) > config.MAX_TICKERS_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {config.MAX_TICKERS_PER_REQUEST} tickers per request"
        )

    results = yfinance_service.get_stock_prices_batch(request.tickers)
    errors = [t for t in request.tickers if t.upper() not in results]

    return StockPriceResponse(
        success=True,
        data={k: StockPrice(**v) for k, v in results.items()},
        errors=errors if errors else None
    )


@router.get("/info/{ticker}", response_model=CompanyInfo)
async def get_company_info(ticker: str):
    """
    Get company information for a ticker
    """
    result = yfinance_service.get_company_info(ticker.upper())
    if not result:
        raise HTTPException(status_code=404, detail=f"Could not fetch info for {ticker}")
    return result


@router.get("/history/{ticker}", response_model=HistoricalPriceResponse)
async def get_historical_prices(
    ticker: str,
    period: str = Query(default="1y", pattern="^(1d|5d|1mo|3mo|6mo|1y|2y|5y|10y|ytd|max)$"),
    interval: str = Query(default="1d", pattern="^(1m|2m|5m|15m|30m|60m|90m|1h|1d|5d|1wk|1mo|3mo)$")
):
    """
    Get historical price data for a ticker

    - period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    - interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
    """
    result = yfinance_service.get_historical_prices(
        ticker.upper(),
        period=period,
        interval=interval
    )
    if not result:
        raise HTTPException(status_code=404, detail=f"Could not fetch history for {ticker}")
    return result


@router.get("/cagr/{ticker}", response_model=CAGRResponse)
async def get_cagr(ticker: str):
    """
    Get Compound Annual Growth Rate (CAGR) for a ticker

    Returns 5-year and 10-year CAGR based on historical price data.
    """
    result = yfinance_service.get_cagr(ticker.upper())
    if not result:
        raise HTTPException(status_code=404, detail=f"Could not calculate CAGR for {ticker}")
    return result


@router.post("/cagr", response_model=CAGRBatchResponse)
async def get_cagr_batch(request: CAGRBatchRequest):
    """
    Get CAGR for multiple tickers (batch).
    Fetches all tickers in parallel for better performance.
    """
    if len(request.tickers) > config.MAX_TICKERS_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {config.MAX_TICKERS_PER_REQUEST} tickers per request"
        )

    results = {}
    errors = []

    # Fetch all tickers in parallel
    loop = asyncio.get_event_loop()

    async def fetch_cagr(ticker: str):
        return await loop.run_in_executor(
            executor,
            yfinance_service.get_cagr,
            ticker.upper()
        )

    # Run all fetches in parallel
    tasks = [fetch_cagr(ticker) for ticker in request.tickers]
    fetched_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    for ticker, result in zip(request.tickers, fetched_results):
        if isinstance(result, Exception):
            errors.append(ticker)
            continue

        if result:
            results[ticker.upper()] = result
        else:
            errors.append(ticker)

    return CAGRBatchResponse(
        success=True,
        data={k: CAGRResponse(**v) for k, v in results.items()},
        errors=errors if errors else None
    )


@router.get("/price-at-date/{ticker}", response_model=PriceAtDateResponse)
async def get_price_at_date(
    ticker: str,
    year: int = Query(..., ge=2000, le=2030, description="Year"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)")
):
    """
    Get the closing price at the end of a specific month

    Useful for historical valuation and growth calculations.
    """
    result = yfinance_service.get_price_at_date(ticker.upper(), year, month)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Could not fetch price for {ticker} at {year}-{month:02d}"
        )
    return result
