import httpx
from typing import Optional

BASE_URL = "https://api.binance.com"

_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(base_url=BASE_URL, timeout=10.0)
    return _client


async def get_exchange_info() -> list[dict]:
    """Fetch all spot trading symbols from Binance."""
    client = get_client()
    response = await client.get("/api/v3/exchangeInfo")
    response.raise_for_status()
    return response.json()["symbols"]


async def get_tickers(symbol: Optional[str] = None) -> list[dict] | dict:
    """Fetch 24h price change statistics."""
    client = get_client()
    params = {"symbol": symbol} if symbol else {}
    response = await client.get("/api/v3/ticker/24hr", params=params)
    response.raise_for_status()
    return response.json()


async def get_klines(symbol: str, interval: str, limit: int = 100) -> list[list]:
    """Fetch candlestick (kline) data for a symbol."""
    client = get_client()
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    response = await client.get("/api/v3/klines", params=params)
    response.raise_for_status()
    return response.json()


def parse_kline(raw: list) -> dict:
    """Parse a raw Binance kline array into a dict."""
    return {
        "open_time": raw[0],
        "open": float(raw[1]),
        "high": float(raw[2]),
        "low": float(raw[3]),
        "close": float(raw[4]),
        "volume": float(raw[5]),
        "close_time": raw[6],
    }


async def close():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
