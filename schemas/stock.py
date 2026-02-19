"""
Pydantic schemas for stock data
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class StockPrice(BaseModel):
    ticker: str
    price: Optional[float] = None
    previous_close: Optional[float] = None
    open: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    volume: Optional[int] = None
    market_cap: Optional[float] = None
    currency: Optional[str] = "USD"
    change: Optional[float] = None
    change_percent: Optional[float] = None
    timestamp: Optional[str] = None


class StockPriceRequest(BaseModel):
    tickers: List[str] = Field(..., min_length=1, max_length=50)


class StockPriceResponse(BaseModel):
    success: bool
    data: Dict[str, StockPrice]
    errors: Optional[List[str]] = None


class DividendEvent(BaseModel):
    date: str
    month: int  # 0-indexed month
    month_name: str
    amount: float  # dividend per share
    is_forecasted: bool = False
    source: Optional[str] = None  # "actual", "announced", "last_year", "historical_avg", "fallback"


class DividendData(BaseModel):
    ticker: str
    year: int
    has_dividends: bool
    frequency: Optional[str] = None  # "monthly", "quarterly", "yearly"
    payment_months: List[int] = []  # 0-indexed months
    dividends: List[DividendEvent] = []
    annual_total_per_share: float = 0
    currency: Optional[str] = "USD"


class DividendRequest(BaseModel):
    tickers: List[str] = Field(..., min_length=1, max_length=50)
    year: Optional[int] = None  # defaults to current year


class DividendResponse(BaseModel):
    success: bool
    year: int
    data: Dict[str, DividendData]
    errors: Optional[List[str]] = None


class CompanyInfo(BaseModel):
    ticker: str
    name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    exchange: Optional[str] = None
    market_cap: Optional[float] = None
    website: Optional[str] = None
    description: Optional[str] = None
    employees: Optional[int] = None
    dividend_yield: Optional[float] = None
    dividend_rate: Optional[float] = None
    ex_dividend_date: Optional[int] = None
    pe_ratio: Optional[float] = None
    forward_pe: Optional[float] = None
    eps: Optional[float] = None
    beta: Optional[float] = None
    week_52_high: Optional[float] = Field(None, alias="52_week_high")
    week_52_low: Optional[float] = Field(None, alias="52_week_low")


class HistoricalPrice(BaseModel):
    date: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None


class HistoricalPriceResponse(BaseModel):
    ticker: str
    period: str
    interval: str
    prices: List[HistoricalPrice]
    currency: Optional[str] = "USD"


# Symbol Search schemas
class SymbolSearchResult(BaseModel):
    symbol: str
    short_name: Optional[str] = None
    long_name: Optional[str] = None
    quote_type: Optional[str] = None
    exchange: Optional[str] = None
    exchange_display: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    score: Optional[float] = None


class SymbolSearchResponse(BaseModel):
    success: bool
    query: str
    count: int
    results: List[SymbolSearchResult]


# CAGR schemas
class CAGRResponse(BaseModel):
    ticker: str
    cagr_5y: Optional[float] = None
    cagr_10y: Optional[float] = None
    cagr_5y_percent: Optional[float] = None
    cagr_10y_percent: Optional[float] = None
    current_price: Optional[float] = None
    currency: Optional[str] = "USD"
    data_points: Optional[int] = None
    years_of_data: Optional[float] = None
    error: Optional[str] = None


class CAGRBatchRequest(BaseModel):
    tickers: List[str] = Field(..., min_length=1, max_length=50)


class CAGRBatchResponse(BaseModel):
    success: bool
    data: Dict[str, CAGRResponse]
    errors: Optional[List[str]] = None


# Price at date schema
class PriceAtDateResponse(BaseModel):
    ticker: str
    date: str
    price: Optional[float] = None
    year: int
    month: int
    currency: Optional[str] = "USD"


