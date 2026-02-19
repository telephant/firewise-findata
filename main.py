"""
Firewise Financial Data Service

A FastAPI service providing financial data via yfinance
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

import config
from routes import stock, dividend, search

app = FastAPI(
    title="Firewise Financial Data Service",
    description="API for fetching financial data including stock prices, dividends, and company info",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(stock.router)
app.include_router(dividend.router)
app.include_router(search.router)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "firewise-findata",
        "status": "healthy",
        "version": "1.0.0",
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
    )
