"""
Dividend routes
"""
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime
from typing import List, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor
from schemas.stock import (
    DividendData, DividendEvent, DividendRequest, DividendResponse
)
from services import yfinance_service
import config

# Thread pool for parallel yfinance calls
executor = ThreadPoolExecutor(max_workers=10)

router = APIRouter(prefix="/dividend", tags=["Dividend"])


@router.get("/{ticker}", response_model=DividendData)
async def get_dividends(
    ticker: str,
    year: Optional[int] = Query(default=None, ge=2000, le=2030, description="Year (defaults to current year)")
):
    """
    Get dividends for a ticker for a specific year.

    Returns both actual (historical) dividends and forecasted future dividends,
    with `is_forecasted` flag to distinguish them.

    - **ticker**: Stock ticker (e.g., AAPL, D05.SI)
    - **year**: Year to get dividends for (defaults to current year)

    Each dividend includes:
    - `date`: Payment date (actual or estimated)
    - `month`: 0-indexed month (0=Jan, 11=Dec)
    - `month_name`: Month name (Jan, Feb, etc.)
    - `amount`: Dividend per share
    - `is_forecasted`: True if forecasted, False if actual
    - `source`: "actual", "announced", "last_year", "historical_avg", or "fallback"
    """
    if year is None:
        year = datetime.now().year

    result = yfinance_service.get_dividends(ticker.upper(), year)
    if not result:
        raise HTTPException(status_code=404, detail=f"Could not fetch dividends for {ticker}")

    return DividendData(
        ticker=result["ticker"],
        year=result["year"],
        has_dividends=result["has_dividends"],
        frequency=result.get("frequency"),
        payment_months=result.get("payment_months", []),
        dividends=[DividendEvent(**d) for d in result.get("dividends", [])],
        annual_total_per_share=result.get("annual_total_per_share", 0),
        currency=result.get("currency", "USD"),
    )


@router.post("/batch", response_model=DividendResponse)
async def get_dividends_batch(request: DividendRequest):
    """
    Get dividends for multiple tickers (batch).

    Returns both actual and forecasted dividends for each ticker.
    Fetches all tickers in parallel for better performance.
    """
    if len(request.tickers) > config.MAX_TICKERS_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {config.MAX_TICKERS_PER_REQUEST} tickers per request"
        )

    year = request.year if request.year else datetime.now().year
    results = {}
    errors = []

    # Fetch all tickers in parallel
    loop = asyncio.get_event_loop()

    async def fetch_dividend(ticker: str):
        return await loop.run_in_executor(
            executor,
            yfinance_service.get_dividends,
            ticker.upper(),
            year
        )

    # Run all fetches in parallel
    tasks = [fetch_dividend(ticker) for ticker in request.tickers]
    fetched_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    for ticker, result in zip(request.tickers, fetched_results):
        if isinstance(result, Exception):
            errors.append(ticker)
            continue

        if result:
            results[ticker.upper()] = DividendData(
                ticker=result["ticker"],
                year=result["year"],
                has_dividends=result["has_dividends"],
                frequency=result.get("frequency"),
                payment_months=result.get("payment_months", []),
                dividends=[DividendEvent(**d) for d in result.get("dividends", [])],
                annual_total_per_share=result.get("annual_total_per_share", 0),
                currency=result.get("currency", "USD"),
            )
        else:
            errors.append(ticker)

    return DividendResponse(
        success=True,
        year=year,
        data=results,
        errors=errors if errors else None
    )
