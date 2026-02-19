"""
Caching utilities for financial data
"""
from cachetools import TTLCache
from typing import Any, Optional
import config

# Separate caches for different data types with different TTLs
stock_price_cache = TTLCache(maxsize=1000, ttl=config.CACHE_TTL_STOCK_PRICE)
dividend_cache = TTLCache(maxsize=500, ttl=config.CACHE_TTL_DIVIDEND)
company_info_cache = TTLCache(maxsize=500, ttl=config.CACHE_TTL_COMPANY_INFO)


def get_cached(cache: TTLCache, key: str) -> Optional[Any]:
    """Get value from cache if exists"""
    return cache.get(key)


def set_cached(cache: TTLCache, key: str, value: Any) -> None:
    """Set value in cache"""
    cache[key] = value


def clear_cache(cache: TTLCache) -> None:
    """Clear all entries from cache"""
    cache.clear()
