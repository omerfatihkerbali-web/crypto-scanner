import sys
from typing import Callable, Awaitable

import pandas_ta as ta
import pandas as pd

from app.binance.client import get_klines, parse_kline
from app.utils.format import signal_message


async def run_signal_scan(
    symbols: list[str],
    config: dict,
    notify: Callable[[str], Awaitable[None]],
) -> None:
    interval: str = config["interval"]
    lookback: int = config["lookbackCandles"]
    rsi_cfg: dict = config["rsi"]
    macd_cfg: dict = config["macd"]
    bb_cfg: dict = config["bollingerBands"]

    for symbol in symbols:
        try:
            raw = await get_klines(symbol, interval, limit=lookback)
            if len(raw) < lookback:
                continue

            klines = [parse_kline(k) for k in raw]
            closes = pd.Series([k["close"] for k in klines], dtype=float)

            triggered: list[str] = []

            # RSI
            if rsi_cfg["enabled"]:
                rsi_series = ta.rsi(closes, length=rsi_cfg["period"])
                if rsi_series is not None and not rsi_series.empty:
                    last_rsi = rsi_series.iloc[-1]
                    if last_rsi >= rsi_cfg["overbought"]:
                        triggered.append(f"RSI {last_rsi:.1f} — Overbought (≥{rsi_cfg['overbought']})")
                    elif last_rsi <= rsi_cfg["oversold"]:
                        triggered.append(f"RSI {last_rsi:.1f} — Oversold (≤{rsi_cfg['oversold']})")

            # MACD
            if macd_cfg["enabled"]:
                macd_df = ta.macd(
                    closes,
                    fast=macd_cfg["fastPeriod"],
                    slow=macd_cfg["slowPeriod"],
                    signal=macd_cfg["signalPeriod"],
                )
                if macd_df is not None and len(macd_df) >= 2:
                    macd_col = [c for c in macd_df.columns if c.startswith("MACD_")][0]
                    sig_col = [c for c in macd_df.columns if c.startswith("MACDs_")][0]

                    prev_macd = macd_df[macd_col].iloc[-2]
                    prev_sig = macd_df[sig_col].iloc[-2]
                    curr_macd = macd_df[macd_col].iloc[-1]
                    curr_sig = macd_df[sig_col].iloc[-1]

                    if prev_macd < prev_sig and curr_macd >= curr_sig:
                        triggered.append("MACD — Bullish Crossover")
                    elif prev_macd > prev_sig and curr_macd <= curr_sig:
                        triggered.append("MACD — Bearish Crossover")

            # Bollinger Bands
            if bb_cfg["enabled"]:
                bb_df = ta.bbands(closes, length=bb_cfg["period"], std=bb_cfg["stdDev"])
                if bb_df is not None and not bb_df.empty:
                    upper_col = [c for c in bb_df.columns if "BBU" in c][0]
                    lower_col = [c for c in bb_df.columns if "BBL" in c][0]

                    upper = bb_df[upper_col].iloc[-1]
                    lower = bb_df[lower_col].iloc[-1]
                    last_close = closes.iloc[-1]

                    if last_close >= upper:
                        triggered.append(f"BB Upper Break — ${last_close:.4g} ≥ ${upper:.4g}")
                    elif last_close <= lower:
                        triggered.append(f"BB Lower Break — ${last_close:.4g} ≤ ${lower:.4g}")

            if triggered:
                await notify(signal_message(symbol, triggered))

        except Exception as e:
            sys.stderr.write(f"Signal scan error [{symbol}]: {e}\n")
