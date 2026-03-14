def build_symbol_list(all_symbols: list[dict], config: dict) -> list[str]:
    """
    Filter Binance symbols based on scanner config.

    - watchlist: if non-empty, only these symbols are returned (exact match)
    - blacklist: substring match — symbol is excluded if it contains any pattern
    - exact_blacklist: exact match — symbol is excluded if it equals any entry
    """
    quote_asset: str = config["quoteAsset"]
    blacklist: list[str] = [p.upper() for p in config.get("blacklist", [])]
    exact_blacklist: set[str] = {s.upper() for s in config.get("exact_blacklist", [])}
    watchlist: list[str] = [s.upper() for s in config.get("watchlist", [])]

    if watchlist:
        return watchlist

    result = []
    for s in all_symbols:
        if s["status"] != "TRADING":
            continue
        if s["quoteAsset"] != quote_asset:
            continue
        symbol = s["symbol"].upper()
        if symbol in exact_blacklist:
            continue
        if any(pattern in symbol for pattern in blacklist):
            continue
        result.append(symbol)

    return result
