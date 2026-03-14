import httpx

_token: str = ""
_chat_id: str = ""
_base_url: str = ""


def init(token: str, chat_id: str) -> None:
    global _token, _chat_id, _base_url
    _token = token
    _chat_id = chat_id
    _base_url = f"https://api.telegram.org/bot{token}"


async def notify(text: str) -> None:
    if not _token:
        raise RuntimeError("Telegram not initialized. Call init() first.")

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{_base_url}/sendMessage",
            json={
                "chat_id": _chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
        )
        response.raise_for_status()
