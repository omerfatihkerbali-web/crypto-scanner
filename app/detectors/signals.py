import sys
import time
from datetime import datetime, timezone
from typing import Callable, Awaitable

import pandas_ta_classic as ta
import pandas as pd

from app.binance.client import get_klines, parse_kline

# symbol -> last alert timestamp (monotonic seconds)
_cooldown_map: dict[str, float] = {}

# Fetch extra candles so all indicators have enough history
# MACD(26,9) needs ~35, we fetch 60 to be safe
LOOKBACK = 60


def _score_symbol(klines: list[dict]) -> tuple[int, dict]:
    """
    Evaluate 5 conditions. Each = 20 points. Max = 100.
    Returns (score, details).
    """
    closes = pd.Series([k["close"] for k in klines], dtype=float)
    highs = pd.Series([k["high"] for k in klines], dtype=float)
    lows = pd.Series([k["low"] for k in klines], dtype=float)
    volumes = pd.Series([k["volume"] for k in klines], dtype=float)

    score = 0
    details: dict = {}

    # 1. Volume Spike: current closed candle volume > 3x avg of previous 20
    current_vol = volumes.iloc[-2]
    avg_vol = volumes.iloc[-22:-2].mean()
    vol_mult = current_vol / avg_vol if avg_vol > 0 else 0.0
    details["vol_mult"] = vol_mult
    if vol_mult > 3.0:
        score += 20

    # 2. RSI(14): 45 ≤ RSI ≤ 68
    rsi_series = ta.rsi(closes, length=14)
    last_rsi = float(rsi_series.iloc[-1]) if rsi_series is not None and not rsi_series.empty else None
    details["rsi"] = last_rsi
    if last_rsi is not None and 45.0 <= last_rsi <= 68.0:
        score += 20

    # 3. MACD bullish cross in last 2 candles
    macd_df = ta.macd(closes, fast=12, slow=26, signal=9)
    details["macd_cross"] = False
    if macd_df is not None and len(macd_df) >= 2:
        macd_col = next(c for c in macd_df.columns if c.startswith("MACD_"))
        sig_col = next(c for c in macd_df.columns if c.startswith("MACDs_"))
        prev_m = macd_df[macd_col].iloc[-2]
        prev_s = macd_df[sig_col].iloc[-2]
        curr_m = macd_df[macd_col].iloc[-1]
        curr_s = macd_df[sig_col].iloc[-1]
        cross = bool(prev_m < prev_s and curr_m >= curr_s)
        details["macd_cross"] = cross
        if cross:
            score += 20

    # 4. Breakout proximity: close within 1.5% of 20-candle highest close
    last_close = float(closes.iloc[-1])
    highest_close = float(closes.iloc[-21:-1].max())
    proximity_pct = (highest_close - last_close) / highest_close * 100 if highest_close > 0 else 999.0
    details["proximity_pct"] = proximity_pct
    details["highest_close"] = highest_close
    if proximity_pct <= 1.5:
        score += 20

    # 5. Squeeze release: BB width > Keltner Channel width
    bb_df = ta.bbands(closes, length=20, std=2)
    details["squeeze"] = False
    if bb_df is not None and not bb_df.empty:
        upper_col = next(c for c in bb_df.columns if "BBU" in c)
        lower_col = next(c for c in bb_df.columns if "BBL" in c)
        bb_width = float(bb_df[upper_col].iloc[-1] - bb_df[lower_col].iloc[-1])

        ema_series = ta.ema(closes, length=20)
        atr_series = ta.atr(highs, lows, closes, length=10)

        if ema_series is not None and atr_series is not None:
            kc_width = 2.0 * 1.5 * float(atr_series.iloc[-1])
            squeeze_released = bb_width > kc_width
            details["squeeze"] = squeeze_released
            if squeeze_released:
                score += 20

    return score, details


def _format_alert(symbol: str, score: int, price: float) -> str:
    sl = price * 0.97
    tp1 = price * 1.05
    tp2 = price * 1.11
    base = symbol.replace("USDT", "").replace("BUSD", "")
    tv_url = f"https://www.tradingview.com/chart/?symbol=BINANCE:{base}USDT&interval=15"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return (
        f"🚨 *PRE-PUMP SİNYALİ*\n"
        f"📊 Coin: `{symbol}`\n"
        f"⭐ Skor: `{score}/100`\n"
        f"💰 Giriş: `${price:.6g}`\n"
        f"🛑 Stop Loss: `${sl:.6g}` (%3 aşağı)\n"
        f"🎯 Hedef 1: `${tp1:.6g}` (%5)\n"
        f"🎯 Hedef 2: `${tp2:.6g}` (%11)\n"
        f"📈 [TradingView]({tv_url})\n"
        f"🕐 {now}"
    )


async def run_signal_scan(
    symbols: list[str],
    config: dict,
    notify: Callable[[str], Awaitable[None]],
) -> None:
    interval: str = config.get("interval", "15m")
    cooldown_sec: float = config.get("cooldownMinutes", 120) * 60
    min_score: int = config.get("minScore", 80)
    now = time.monotonic()

    for symbol in symbols:
        try:
            # Skip cooldown symbols without hitting the API
            if now - _cooldown_map.get(symbol, 0.0) < cooldown_sec:
                continue

            raw = await get_klines(symbol, interval, limit=LOOKBACK)
            if len(raw) < LOOKBACK:
                continue

            klines = [parse_kline(k) for k in raw]
            price = klines[-1]["close"]

            score, _ = _score_symbol(klines)

            if score >= min_score:
                _cooldown_map[symbol] = now
                await notify(_format_alert(symbol, score, price))

        except Exception as e:
            sys.stderr.write(f"Signal scan error [{symbol}]: {e}\n")
