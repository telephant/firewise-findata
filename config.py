"""
Configuration for firewise-findata service
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Server settings
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8002))
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Cache settings (in seconds)
CACHE_TTL_STOCK_PRICE = int(os.getenv("CACHE_TTL_STOCK_PRICE", 60))  # 1 minute
CACHE_TTL_DIVIDEND = int(os.getenv("CACHE_TTL_DIVIDEND", 3600))  # 1 hour
CACHE_TTL_COMPANY_INFO = int(os.getenv("CACHE_TTL_COMPANY_INFO", 86400))  # 24 hours

# Rate limiting
MAX_TICKERS_PER_REQUEST = int(os.getenv("MAX_TICKERS_PER_REQUEST", 50))
