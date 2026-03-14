import asyncio
import sys
import time
from typing import Callable, Awaitable

from app.binance.client import get_tickers
from app.utils.format import pump_message, report_message

# symbol -> last alert timestamp (epoch seconds)
_cooldown_map: dict[str, float] = {}


async def run_pump_scan(
    symbols: list[str],
    config: dict,
    notify: Callable[[str], Awaitable[None]],
) -> None:
    pump_threshold: float = config["pumpThreshold"]
    dump_threshold: float = config["dumpThreshold"]
    cooldown_sec: float = config["cooldownMinutes"] * 60

    try:
        tickers: list[dict] = await get_tickers()
    except Exception as e:
        raise RuntimeError(f"Ticker fetch failed: {e}") from e

    symbol_set = set(symbols)
    now = time.monotonic()

    for ticker in tickers:
        symbol = ticker["symbol"]
        if symbol not in symbol_set:
            continue

        change_pct = float(ticker["priceChangePercent"])
        price = float(ticker["lastPrice"])

        is_pump = change_pct >= pump_threshold
        is_dump = change_pct <= dump_threshold

        if not is_pump and not is_dump:
            continue

        last_alert = _cooldown_map.get(symbol, 0.0)
        if now - last_alert < cooldown_sec:
            continue

        _cooldown_map[symbol] = now
        direction = "pump" if is_pump else "dump"

        try:
            await notify(pump_message(symbol, change_pct, price, direction))
        except Exception as e:
            sys.stderr.write(f"Notify error [{symbol}]: {e}\n")


async def run_pump_report(
    symbols: list[str],
    top_n: int,
    notify: Callable[[str], Awaitable[None]],
) -> None:
    try:
        tickers: list[dict] = await get_tickers()
    except Exception as e:
        raise RuntimeError(f"Ticker fetch failed: {e}") from e

    symbol_set = set(symbols)
    movers = [
        {"symbol": t["symbol"], "change_pct": float(t["priceChangePercent"])}
        for t in tickers
        if t["symbol"] in symbol_set
    ]
    movers.sort(key=lambda x: x["change_pct"], reverse=True)

    pumps = [m for m in movers if m["change_pct"] > 0][:top_n]
    dumps = list(reversed([m for m in movers if m["change_pct"] < 0]))[:top_n]

    await notify(report_message(pumps, dumps, period="24h"))
