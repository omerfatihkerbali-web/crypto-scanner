import sys
from typing import Callable, Awaitable

from app.binance.client import get_klines, parse_kline
from app.utils.format import volume_message


async def run_volume_scan(
    symbols: list[str],
    config: dict,
    notify: Callable[[str], Awaitable[None]],
) -> None:
    interval: str = config["interval"]
    lookback: int = config["lookbackCandles"]
    spike_multiplier: float = config["spikeMultiplier"]

    for symbol in symbols:
        try:
            raw = await get_klines(symbol, interval, limit=lookback + 1)
            if len(raw) < lookback + 1:
                continue

            klines = [parse_kline(k) for k in raw]

            # Second-to-last = most recent CLOSED candle
            current_vol = klines[-2]["volume"]
            history_vols = [k["volume"] for k in klines[:-2]]

            if not history_vols:
                continue

            avg_vol = sum(history_vols) / len(history_vols)
            if avg_vol == 0:
                continue

            multiplier = current_vol / avg_vol

            if multiplier >= spike_multiplier:
                await notify(volume_message(symbol, current_vol, avg_vol, multiplier))

        except Exception as e:
            sys.stderr.write(f"Volume scan error [{symbol}]: {e}\n")
