def tradingview_url(symbol: str, interval: str = "60") -> str:
    base = symbol.replace("USDT", "").replace("BUSD", "")
    return f"https://www.tradingview.com/chart/?symbol=BINANCE:{base}USDT&interval={interval}"


def pump_message(symbol: str, change_pct: float, price: float, direction: str) -> str:
    emoji = "🚀" if direction == "pump" else "🔻"
    sign = "+" if change_pct > 0 else ""
    return (
        f"{emoji} *{symbol}* — {direction.upper()}\n"
        f"Price: `${price:.6g}`\n"
        f"Change: `{sign}{change_pct:.2f}%`\n"
        f"📊 [Chart]({tradingview_url(symbol)})"
    )


def volume_message(symbol: str, current_vol: float, avg_vol: float, multiplier: float) -> str:
    return (
        f"📊 *{symbol}* — VOLUME SPIKE\n"
        f"Current: `{current_vol:,.0f}`\n"
        f"24h Avg: `{avg_vol:,.0f}`\n"
        f"Spike: `{multiplier:.1f}x`\n"
        f"📊 [Chart]({tradingview_url(symbol)})"
    )


def signal_message(symbol: str, signals: list[str]) -> str:
    lines = "\n".join(f"• {s}" for s in signals)
    return (
        f"🔔 *{symbol}* — SIGNALS\n"
        f"{lines}\n"
        f"📊 [Chart]({tradingview_url(symbol)})"
    )


def report_message(pumps: list[dict], dumps: list[dict], period: str = "24h") -> str:
    top_pumps = "\n".join(
        f"{i+1}. *{p['symbol']}* `+{p['change_pct']:.2f}%`"
        for i, p in enumerate(pumps[:5])
    ) or "None"

    top_dumps = "\n".join(
        f"{i+1}. *{d['symbol']}* `{d['change_pct']:.2f}%`"
        for i, d in enumerate(dumps[:5])
    ) or "None"

    return (
        f"📈 *Top Pumps ({period})*\n{top_pumps}\n\n"
        f"📉 *Top Dumps ({period})*\n{top_dumps}"
    )
