"""
yfinance service for fetching financial data
"""
import yfinance as yf
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
from utils.cache import (
    stock_price_cache, dividend_cache, company_info_cache,
    get_cached, set_cached
)


def get_stock_price(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Get current stock price and basic info
    """
    cache_key = f"price:{ticker}"
    cached = get_cached(stock_price_cache, cache_key)
    if cached:
        return cached

    try:
        stock = yf.Ticker(ticker)
        info = stock.fast_info

        _qt_map = {"EQUITY": "stock", "ETF": "etf", "FUTURE": "future", "CRYPTOCURRENCY": "crypto", "INDEX": "index", "CURRENCY": "currency", "MUTUALFUND": "fund"}
        raw_quote_type = getattr(info, 'quote_type', None)
        quote_type = _qt_map.get(raw_quote_type, None) if raw_quote_type else None

        result = {
            "ticker": ticker.upper(),
            "price": info.last_price,
            "previous_close": info.previous_close,
            "open": info.open,
            "day_high": info.day_high,
            "day_low": info.day_low,
            "volume": info.last_volume,
            "market_cap": info.market_cap,
            "currency": info.currency,
            "change": info.last_price - info.previous_close if info.last_price and info.previous_close else None,
            "change_percent": ((info.last_price - info.previous_close) / info.previous_close * 100) if info.last_price and info.previous_close else None,
            "timestamp": datetime.now().isoformat(),
            "quote_type": quote_type,
        }

        set_cached(stock_price_cache, cache_key, result)
        return result
    except Exception as e:
        import traceback
        print(f"Error fetching price for {ticker}: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        return None


# Ticker suffix to currency mapping
TICKER_SUFFIX_CURRENCY = {
    ".SI": "SGD",   # Singapore
    ".HK": "HKD",   # Hong Kong
    ".T": "JPY",    # Tokyo
    ".L": "GBP",    # London
    ".AX": "AUD",   # Australia
    ".TO": "CAD",   # Toronto
    ".V": "CAD",    # TSX Venture
    ".DE": "EUR",   # Germany
    ".PA": "EUR",   # Paris
    ".AS": "EUR",   # Amsterdam
    ".MI": "EUR",   # Milan
    ".MC": "EUR",   # Madrid
    ".SW": "CHF",   # Swiss
    ".KS": "KRW",   # Korea
    ".TW": "TWD",   # Taiwan
    ".NS": "INR",   # India NSE
    ".BO": "INR",   # India BSE
    ".SA": "BRL",   # Brazil
    ".MX": "MXN",   # Mexico
}


def _get_currency_from_ticker(ticker: str) -> str:
    """Get currency from ticker suffix (fast, no API call)"""
    ticker_upper = ticker.upper()
    for suffix, currency in TICKER_SUFFIX_CURRENCY.items():
        if ticker_upper.endswith(suffix.upper()):
            return currency
    return "USD"  # Default for US stocks (no suffix)


def get_stock_prices_batch(tickers: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Get prices for multiple tickers using parallel single-ticker fetches.
    This is more reliable than yf.download() which can fail silently for some tickers.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = {}
    uncached_tickers = []

    # Check cache first
    for ticker in tickers:
        cache_key = f"price:{ticker}"
        cached = get_cached(stock_price_cache, cache_key)
        if cached:
            results[ticker.upper()] = cached
        else:
            uncached_tickers.append(ticker)

    # Fetch uncached tickers in parallel
    if uncached_tickers:
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_ticker = {
                executor.submit(get_stock_price, ticker): ticker
                for ticker in uncached_tickers
            }

            for future in as_completed(future_to_ticker):
                ticker = future_to_ticker[future]
                try:
                    result = future.result()
                    if result:
                        results[ticker.upper()] = result
                except Exception as e:
                    print(f"Error fetching {ticker}: {e}")

    return results


def get_dividends(ticker: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """
    Get dividends for a ticker for a specific year.

    Returns both historical (actual) dividends and forecasted future dividends,
    with is_forecasted flag to distinguish them.

    Args:
        ticker: Stock ticker
        year: Year to get dividends for (defaults to current year)

    Returns:
        Dict with all dividends for the year (actual + forecasted)
    """
    if year is None:
        year = datetime.now().year

    cache_key = f"dividend:{ticker}:{year}"
    cached = get_cached(dividend_cache, cache_key)
    if cached:
        return cached

    try:
        stock = yf.Ticker(ticker)
        currency = _get_ticker_currency(stock)

        # Get 5 years of dividend history for pattern detection
        all_dividends = stock.dividends

        if all_dividends.empty:
            result = {
                "ticker": ticker.upper(),
                "year": year,
                "has_dividends": False,
                "frequency": None,
                "payment_months": [],
                "dividends": [],
                "annual_total_per_share": 0,
                "currency": currency,
                "next_ex_date": None,
            }
            set_cached(dividend_cache, cache_key, result)
            return result

        # Filter to last 5 years for pattern detection
        five_years_ago = datetime.now() - timedelta(days=5 * 365)
        filtered_dividends = all_dividends[all_dividends.index >= five_years_ago.strftime('%Y-%m-%d')]

        # Convert to list of events
        dividend_events = [
            {"date": idx.to_pydatetime(), "amount": float(val)}
            for idx, val in filtered_dividends.items()
        ]

        # Detect pattern
        pattern = _detect_dividend_pattern(dividend_events, year)

        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                       "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

        # Build unified dividend list for the requested year
        now = datetime.now()
        current_year = now.year
        current_month = now.month - 1  # 0-indexed

        dividends = []

        # Get actual dividends for this year from history
        actual_months_covered = set()
        for e in dividend_events:
            if e["date"].year == year:
                month = e["date"].month - 1  # 0-indexed
                # Check if this is actually in the past (received) or future (announced)
                event_date = e["date"]
                if hasattr(event_date, 'tzinfo') and event_date.tzinfo is not None:
                    event_date = event_date.replace(tzinfo=None)

                is_past = event_date <= now

                dividends.append({
                    "date": e["date"].strftime('%Y-%m-%d'),
                    "month": month,
                    "month_name": month_names[month],
                    "amount": round(e["amount"], 6),
                    "is_forecasted": not is_past,  # If in future, it's announced but not received
                    "source": "actual" if is_past else "announced",
                })
                actual_months_covered.add(month)

        # Add forecasts for remaining payment months
        if pattern["frequency"] and pattern["payment_months"]:
            for month in pattern["payment_months"]:
                # Skip if we already have actual/announced data for this month
                if month in actual_months_covered:
                    continue

                # Skip past months in current year (no dividend = no dividend)
                if year == current_year and month < current_month:
                    continue

                # Skip all months for past years
                if year < current_year:
                    continue

                # Determine forecast amount using priority:
                # 1. Last year same month (baseline)
                # 2. Historical average
                # 3. Last dividend (fallback)
                last_year_amount = pattern["last_year_by_month"].get(month)
                avg_amount = pattern["avg_by_month"].get(month)

                if last_year_amount and last_year_amount > 0:
                    amount = last_year_amount
                    source = "last_year"
                elif avg_amount:
                    amount = avg_amount
                    source = "historical_avg"
                else:
                    amount = pattern["last_dividend"]
                    source = "fallback"

                dividends.append({
                    "date": f"{year}-{month+1:02d}-15",  # Estimated mid-month
                    "month": month,
                    "month_name": month_names[month],
                    "amount": round(amount, 6),
                    "is_forecasted": True,
                    "source": source,
                })

        # Sort by month
        dividends.sort(key=lambda x: x["month"])

        annual_total = sum(d["amount"] for d in dividends)

        # Get next ex-dividend date from Yahoo Finance info (Unix timestamp → ISO date)
        next_ex_date = None
        try:
            info = stock.info
            ex_ts = info.get("exDividendDate")
            if ex_ts and ex_ts > 0:
                next_ex_date = datetime.utcfromtimestamp(ex_ts).strftime('%Y-%m-%d')
        except Exception:
            pass

        result = {
            "ticker": ticker.upper(),
            "year": year,
            "has_dividends": True,
            "frequency": pattern["frequency"],
            "payment_months": pattern["payment_months"],
            "dividends": dividends,
            "annual_total_per_share": round(annual_total, 6),
            "currency": currency,
            "next_ex_date": next_ex_date,
        }

        set_cached(dividend_cache, cache_key, result)
        return result
    except Exception as e:
        print(f"Error fetching dividends for {ticker}: {e}")
        return None


def get_company_info(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Get company information
    """
    cache_key = f"info:{ticker}"
    cached = get_cached(company_info_cache, cache_key)
    if cached:
        return cached

    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        result = {
            "ticker": ticker.upper(),
            "name": info.get("longName") or info.get("shortName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "currency": info.get("currency"),
            "exchange": info.get("exchange"),
            "market_cap": info.get("marketCap"),
            "website": info.get("website"),
            "description": info.get("longBusinessSummary"),
            "employees": info.get("fullTimeEmployees"),
            "dividend_yield": info.get("dividendYield"),
            "dividend_rate": info.get("dividendRate"),
            "ex_dividend_date": info.get("exDividendDate"),
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "eps": info.get("trailingEps"),
            "beta": info.get("beta"),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
        }

        set_cached(company_info_cache, cache_key, result)
        return result
    except Exception as e:
        print(f"Error fetching info for {ticker}: {e}")
        return None


def get_historical_prices(
    ticker: str,
    period: str = "1y",
    interval: str = "1d"
) -> Optional[Dict[str, Any]]:
    """
    Get historical price data

    period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    interval: 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period, interval=interval)

        if hist.empty:
            return None

        prices = [
            {
                "date": idx.strftime('%Y-%m-%d') if interval in ['1d', '5d', '1wk', '1mo', '3mo'] else idx.isoformat(),
                "open": float(row['Open']) if pd.notna(row['Open']) else None,
                "high": float(row['High']) if pd.notna(row['High']) else None,
                "low": float(row['Low']) if pd.notna(row['Low']) else None,
                "close": float(row['Close']) if pd.notna(row['Close']) else None,
                "volume": int(row['Volume']) if pd.notna(row['Volume']) else None,
            }
            for idx, row in hist.iterrows()
        ]

        return {
            "ticker": ticker.upper(),
            "period": period,
            "interval": interval,
            "prices": prices,
            "currency": _get_ticker_currency(stock),
        }
    except Exception as e:
        print(f"Error fetching historical prices for {ticker}: {e}")
        return None


def _get_ticker_currency(stock: yf.Ticker) -> str:
    """Get currency for a ticker (uses fast suffix mapping first, falls back to API)"""
    # First try fast suffix mapping
    ticker = stock.ticker if hasattr(stock, 'ticker') else ""
    suffix_currency = _get_currency_from_ticker(ticker)
    if suffix_currency != "USD" or not ticker or "." not in ticker:
        # Either we found a non-USD currency from suffix, or it's a US stock
        return suffix_currency

    # Fallback to API for unknown suffixes
    try:
        info = stock.fast_info
        return info.currency or "USD"
    except:
        return "USD"


def _detect_dividend_pattern(dividend_events: List[Dict], forecast_year: int) -> Dict[str, Any]:
    """
    Detect dividend payment pattern from historical data

    Returns:
        Dict with frequency, payment_months, amounts by month, etc.
    """
    if not dividend_events:
        return {
            "frequency": None,
            "payment_months": [],
            "last_dividend": 0,
            "avg_by_month": {},
            "last_year_by_month": {},
            "upcoming_by_month": {},
        }

    now = datetime.now()
    baseline_year = forecast_year - 1

    # Helper to compare dates (handle timezone-aware vs naive)
    def is_future(event_date: datetime) -> bool:
        # Remove timezone info for comparison
        if hasattr(event_date, 'tzinfo') and event_date.tzinfo is not None:
            event_date = event_date.replace(tzinfo=None)
        return event_date > now

    # Separate upcoming (future) vs historical dividends
    upcoming_events = [e for e in dividend_events
                       if is_future(e["date"]) and e["date"].year == forecast_year]
    historical_events = [e for e in dividend_events if not is_future(e["date"])]

    # Store upcoming dividends by month
    upcoming_by_month = {}
    for e in upcoming_events:
        upcoming_by_month[e["date"].month - 1] = e["amount"]  # 0-indexed month

    # Detect frequency from historical dates
    dates = [e["date"] for e in historical_events]
    frequency = _detect_frequency(dates)

    # Get payment months
    payment_months = _get_payment_months(dates, frequency) if frequency else []

    # Get last dividend
    sorted_by_date = sorted(historical_events, key=lambda x: x["date"], reverse=True)
    last_dividend = sorted_by_date[0]["amount"] if sorted_by_date else 0

    # Calculate average amount by month
    month_amounts: Dict[int, List[float]] = {}
    for e in historical_events:
        month = e["date"].month - 1  # 0-indexed
        if month not in month_amounts:
            month_amounts[month] = []
        month_amounts[month].append(e["amount"])

    avg_by_month = {
        month: sum(amounts) / len(amounts)
        for month, amounts in month_amounts.items()
    }

    # Get baseline year's dividend by month
    last_year_by_month = {}
    for e in historical_events:
        if e["date"].year == baseline_year:
            last_year_by_month[e["date"].month - 1] = e["amount"]

    # Calculate data years
    if dates:
        min_date = min(dates)
        max_date = max(dates)
        data_years = (max_date - min_date).days / 365
    else:
        data_years = 0

    return {
        "frequency": frequency,
        "payment_months": payment_months,
        "last_dividend": last_dividend,
        "avg_by_month": avg_by_month,
        "last_year_by_month": last_year_by_month,
        "upcoming_by_month": upcoming_by_month,
        "data_years": round(data_years, 1),
    }


def _detect_frequency(dates: List[datetime]) -> Optional[str]:
    """Detect dividend payment frequency from dates"""
    if len(dates) < 2:
        return None

    # Remove timezone info for comparison
    naive_dates = []
    for d in dates:
        if hasattr(d, 'tzinfo') and d.tzinfo is not None:
            naive_dates.append(d.replace(tzinfo=None))
        else:
            naive_dates.append(d)

    sorted_dates = sorted(naive_dates)
    gaps = []
    for i in range(1, len(sorted_dates)):
        gap_days = (sorted_dates[i] - sorted_dates[i-1]).days
        gap_months = gap_days / 30.44
        gaps.append(gap_months)

    avg_gap = sum(gaps) / len(gaps)

    if avg_gap <= 0.5:
        return "weekly"
    elif avg_gap <= 0.75:
        return "biweekly"
    elif avg_gap <= 1.5:
        return "monthly"
    elif avg_gap <= 4:
        return "quarterly"
    else:
        return "yearly"


def _get_payment_months(dates: List[datetime], frequency: str) -> List[int]:
    """Get typical payment months based on historical data"""
    month_counts: Dict[int, int] = {}
    for d in dates:
        month = d.month - 1  # 0-indexed
        month_counts[month] = month_counts.get(month, 0) + 1

    sorted_months = sorted(month_counts.items(), key=lambda x: x[1], reverse=True)

    if frequency in ["weekly", "biweekly", "monthly"]:
        return list(range(12))  # All months
    elif frequency == "quarterly":
        return [m for m, _ in sorted_months[:4]]
    elif frequency == "yearly":
        return [m for m, _ in sorted_months[:1]]
    else:
        return [m for m, _ in sorted_months]


# Regional exchange mappings for filtering search results
REGIONAL_EXCHANGES = {
    "US": ["NMS", "NYQ", "PCX", "NGM", "NCM", "BTS", "ASE", "NYS", "NAS", "NASDAQ", "NYSE"],
    "SG": ["SES", "SGX"],
    "HK": ["HKG", "HKSE"],
    "UK": ["LSE", "IOB", "LON"],
    "JP": ["TYO", "JPX", "TSE"],
    "CN": ["SHH", "SHZ", "SHA", "SZA"],
    "AU": ["ASX", "AXS"],
    "CA": ["TOR", "TSX", "CVE"],
    "DE": ["GER", "FRA", "ETR"],
    "FR": ["PAR", "EPA"],
}

# Quote type mapping from Yahoo to our types
QUOTE_TYPE_MAP = {
    "EQUITY": "stock",
    "ETF": "etf",
    "FUTURE": "future",
    "CRYPTOCURRENCY": "crypto",
    "INDEX": "index",
    "CURRENCY": "currency",
    "MUTUALFUND": "fund",
}


def search_symbols(
    query: str,
    region: Optional[str] = None,
    quote_type: Optional[str] = None,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search for stock symbols by name or ticker

    Args:
        query: Search term (ticker or company name)
        region: Filter by region (US, SG, HK, UK, JP, CN, AU, CA, DE, FR)
        quote_type: Filter by type (stock, etf, crypto, index, currency, fund) - can be comma-separated
        limit: Max results (default 10, max 20)

    Returns:
        List of matching symbols with metadata
    """
    try:
        # Use yf.Lookup for single type searches (better results for short queries)
        # For multi-type (e.g., "stock,etf"), use yf.Search with filtering
        if quote_type and ',' not in quote_type:
            return _lookup_by_type(query, quote_type, limit)

        # Parse multiple types if provided
        allowed_types = None
        if quote_type:
            allowed_types = set(t.strip() for t in quote_type.split(','))

        # Use yf.Search for general/region-filtered/multi-type searches
        search = yf.Search(query, max_results=min(limit * 3, 50))

        results = []

        # Process quotes
        for quote in search.quotes:
            symbol = quote.get("symbol", "")
            exchange = quote.get("exchange", "")
            yf_quote_type = quote.get("quoteType", "")

            # Map quote type
            mapped_type = QUOTE_TYPE_MAP.get(yf_quote_type, "other")

            # Filter by type(s) if specified
            if allowed_types and mapped_type not in allowed_types:
                continue

            # Filter by region if specified
            if region and region.upper() in REGIONAL_EXCHANGES:
                valid_exchanges = REGIONAL_EXCHANGES[region.upper()]
                if not any(ex in exchange.upper() for ex in valid_exchanges):
                    continue

            result = {
                "symbol": symbol,
                "short_name": quote.get("shortname"),
                "long_name": quote.get("longname"),
                "quote_type": mapped_type,
                "exchange": exchange,
                "exchange_display": quote.get("exchDisp"),
                "sector": quote.get("sector"),
                "industry": quote.get("industry"),
                "score": quote.get("score", 0),
            }

            results.append(result)

            if len(results) >= limit:
                break

        # Sort by score (relevance)
        results.sort(key=lambda x: x.get("score", 0), reverse=True)

        return results[:limit]
    except Exception as e:
        print(f"Error searching symbols for '{query}': {e}")
        return []


def _lookup_by_type(query: str, quote_type: str, limit: int) -> List[Dict[str, Any]]:
    """
    Use yf.Lookup for type-specific searches.
    This provides better results for crypto, etf, etc. even with short queries.
    """
    import pandas as pd

    def safe_str(val):
        """Convert pandas value to string, handling NaN."""
        if pd.isna(val):
            return None
        return str(val) if val is not None else None

    lookup = yf.Lookup(query)

    # Map our type to Lookup method
    type_method_map = {
        "crypto": "get_cryptocurrency",
        "etf": "get_etf",
        "stock": "get_stock",
        "index": "get_index",
        "currency": "get_currency",
        "fund": "get_mutualfund",
        "future": "get_future",
    }

    method_name = type_method_map.get(quote_type)
    if not method_name or not hasattr(lookup, method_name):
        # Fallback to get_all and filter
        df = lookup.get_all(count=limit * 3)
    else:
        method = getattr(lookup, method_name)
        df = method(count=limit)

    if df is None or df.empty:
        return []

    results = []
    for symbol, row in df.iterrows():
        results.append({
            "symbol": symbol,
            "short_name": safe_str(row.get("shortName")),
            "long_name": safe_str(row.get("longName")),
            "quote_type": quote_type,
            "exchange": safe_str(row.get("exchange")),
            "exchange_display": safe_str(row.get("exchDisp")),
            "sector": safe_str(row.get("sector")),
            "industry": safe_str(row.get("industry")),
            "score": float(row.get("score", 0)) if not pd.isna(row.get("score", 0)) else 0.0,
        })

    return results[:limit]


def get_cagr(ticker: str) -> Optional[Dict[str, Any]]:
    """
    Calculate Compound Annual Growth Rate (CAGR) for 5-year and 10-year periods

    CAGR = (End Value / Start Value) ^ (1 / Years) - 1

    Returns:
        Dict with 5y and 10y CAGR rates, or None if error
    """
    try:
        stock = yf.Ticker(ticker)

        # Get 10 years of monthly data for CAGR calculation
        hist = stock.history(period="10y", interval="1mo")

        if hist.empty or len(hist) < 12:  # Need at least 1 year of data
            return {
                "ticker": ticker.upper(),
                "cagr_5y": None,
                "cagr_10y": None,
                "current_price": None,
                "currency": "USD",
                "error": "Insufficient historical data",
            }

        # Get current price and currency
        try:
            fast_info = stock.fast_info
            current_price = fast_info.last_price
            currency = fast_info.currency or "USD"
        except:
            current_price = float(hist['Close'].iloc[-1]) if not hist.empty else None
            currency = "USD"

        # Calculate 5-year CAGR
        cagr_5y = None
        if len(hist) >= 60:  # 5 years * 12 months
            try:
                end_price = float(hist['Close'].iloc[-1])
                start_price = float(hist['Close'].iloc[-60])
                if start_price > 0 and end_price > 0:
                    cagr_5y = (end_price / start_price) ** (1 / 5) - 1
            except:
                pass

        # Calculate 10-year CAGR
        cagr_10y = None
        if len(hist) >= 120:  # 10 years * 12 months
            try:
                end_price = float(hist['Close'].iloc[-1])
                start_price = float(hist['Close'].iloc[-120])
                if start_price > 0 and end_price > 0:
                    cagr_10y = (end_price / start_price) ** (1 / 10) - 1
            except:
                pass

        # Get data points for verification
        data_points = len(hist)
        years_of_data = data_points / 12

        return {
            "ticker": ticker.upper(),
            "cagr_5y": round(cagr_5y, 4) if cagr_5y is not None else None,
            "cagr_10y": round(cagr_10y, 4) if cagr_10y is not None else None,
            "cagr_5y_percent": round(cagr_5y * 100, 2) if cagr_5y is not None else None,
            "cagr_10y_percent": round(cagr_10y * 100, 2) if cagr_10y is not None else None,
            "current_price": current_price,
            "currency": currency,
            "data_points": data_points,
            "years_of_data": round(years_of_data, 1),
        }
    except Exception as e:
        print(f"Error calculating CAGR for {ticker}: {e}")
        return None


def get_price_at_time(ticker: str, minutes_after_open: int = 0) -> Optional[Dict[str, Any]]:
    """
    Get stock price at a specific number of minutes after market open today.

    minutes_after_open == 0 → open price (from fast_info.open)
    minutes_after_open == N → price of the N-th 1-minute bar after the first bar of the session

    Args:
        ticker: Stock ticker (yfinance format, e.g. "AAPL", "D05.SI", "0700.HK")
        minutes_after_open: Minutes after market open (0 = open price)

    Returns:
        Dict with price and metadata, or None on error
    """
    try:
        stock = yf.Ticker(ticker)
        currency = _get_ticker_currency(stock)

        if minutes_after_open == 0:
            # Return today's open price directly from fast_info (no intraday fetch needed)
            info = stock.fast_info
            price = info.open
            if price is None or (isinstance(price, float) and price != price):  # NaN check
                price = info.last_price
            return {
                "ticker": ticker.upper(),
                "price": float(price) if price else None,
                "reference": "open",
                "minutes_after_open": 0,
                "currency": info.currency or currency,
                "timestamp": datetime.now().isoformat(),
            }

        # Fetch today's 1-minute data
        # Use period="1d" so yfinance returns bars in the exchange's local timezone.
        hist = stock.history(period="1d", interval="1m")

        if hist.empty:
            # Market not open yet or holiday — fallback to last known price
            info = stock.fast_info
            return {
                "ticker": ticker.upper(),
                "price": float(info.last_price) if info.last_price else None,
                "reference": "fallback",
                "minutes_after_open": minutes_after_open,
                "currency": info.currency or currency,
                "timestamp": datetime.now().isoformat(),
            }

        # Filter to the most recent trading session.
        # yfinance returns timezone-aware timestamps (exchange local TZ).
        # Normalise to midnight in the same TZ, then pick the latest date present.
        # This avoids the bug where datetime.now().date() (system-local) doesn't
        # match the exchange-local date of the bars.
        index_tz = hist.index.tz  # e.g. America/New_York, Asia/Singapore
        if index_tz is not None:
            # Get the most recent trading date in the exchange's timezone
            latest_date = hist.index[-1].date()
            session_bars = hist[hist.index.date == latest_date]
        else:
            session_bars = hist

        if session_bars.empty:
            session_bars = hist

        # The first bar in the session is bar 0 (market open).
        # Bar N = N minutes after open.
        if len(session_bars) <= minutes_after_open:
            # Requested minute hasn't arrived yet — use latest available bar
            row = session_bars.iloc[-1]
            actual_minutes = len(session_bars) - 1
        else:
            row = session_bars.iloc[minutes_after_open]
            actual_minutes = minutes_after_open

        price = float(row['Close']) if pd.notna(row['Close']) else None
        ts = row.name.isoformat() if hasattr(row.name, 'isoformat') else datetime.now().isoformat()

        return {
            "ticker": ticker.upper(),
            "price": price,
            "reference": "delay",
            "minutes_after_open": actual_minutes,
            "currency": currency,
            "timestamp": ts,
        }
    except Exception as e:
        print(f"Error fetching price at time for {ticker}: {e}")
        return None


def get_price_at_date(ticker: str, year: int, month: int) -> Optional[Dict[str, Any]]:
    """
    Get the closing price at the end of a specific month

    Args:
        ticker: Stock ticker
        year: Year (e.g., 2024)
        month: Month (1-12)

    Returns:
        Dict with price and date info
    """
    try:
        stock = yf.Ticker(ticker)

        # Calculate date range for the month
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)

        # Fetch daily data for the month
        hist = stock.history(start=start_date, end=end_date, interval="1d")

        if hist.empty:
            return None

        # Get the last trading day of the month
        last_row = hist.iloc[-1]
        last_date = hist.index[-1]

        return {
            "ticker": ticker.upper(),
            "date": last_date.strftime('%Y-%m-%d'),
            "price": float(last_row['Close']) if pd.notna(last_row['Close']) else None,
            "year": year,
            "month": month,
            "currency": _get_ticker_currency(stock),
        }
    except Exception as e:
        print(f"Error fetching price at date for {ticker}: {e}")
        return None
