import os
import yaml
from pathlib import Path


def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config.yml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    telegram_token = os.environ.get("TELEGRAM_TOKEN", "").strip()
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not telegram_token or not telegram_chat_id:
        raise RuntimeError("TELEGRAM_TOKEN and TELEGRAM_CHAT_ID must be set in environment")

    config["telegram"] = {
        "token": telegram_token,
        "chat_id": telegram_chat_id,
    }

    return config
