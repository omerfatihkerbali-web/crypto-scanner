import asyncio
import sys
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import load_config
from app.binance.client import get_exchange_info, close as close_client
from app.utils.filter import build_symbol_list
from app.detectors.pump import run_pump_scan, run_pump_report
from app.detectors.volume import run_volume_scan
from app.detectors.signals import run_signal_scan
import app.notifications.telegram as telegram


def parse_cron(expression: str) -> CronTrigger:
    parts = expression.split()
    return CronTrigger(
        minute=parts[0],
        hour=parts[1],
        day=parts[2],
        month=parts[3],
        day_of_week=parts[4],
    )


async def pump_loop(symbols: list[str], config: dict) -> None:
    poll_sec: int = config["pollIntervalSeconds"]
    while True:
        try:
            await run_pump_scan(symbols, config, telegram.notify)
        except Exception as e:
            sys.stderr.write(f"Pump scan error: {e}\n")
        await asyncio.sleep(poll_sec)


async def signal_loop(symbols: list[str], config: dict) -> None:
    poll_sec: int = config["pollIntervalSeconds"]
    while True:
        try:
            await run_signal_scan(symbols, config, telegram.notify)
        except Exception as e:
            sys.stderr.write(f"Signal scan error: {e}\n")
        await asyncio.sleep(poll_sec)


async def main() -> None:
    config = load_config()
    telegram.init(config["telegram"]["token"], config["telegram"]["chat_id"])

    print("Fetching active symbols from Binance...")
    all_symbols = await get_exchange_info()
    symbols = build_symbol_list(all_symbols, config["scanner"])
    quote = config["scanner"]["quoteAsset"]
    print(f"Tracking {len(symbols)} {quote} pairs")

    scheduler = AsyncIOScheduler()

    # Pump scanner: polling loop
    if config["pump"]["enabled"]:
        poll_sec = config["pump"]["pollIntervalSeconds"]
        print(f"Pump scanner: polling every {poll_sec}s")
        asyncio.create_task(pump_loop(symbols, config["pump"]))

        if config["pump"]["report"]["enabled"]:
            schedule = config["pump"]["report"]["schedule"]
            top_n = config["pump"]["report"]["topN"]
            print(f'Pump report: cron "{schedule}"')
            scheduler.add_job(
                run_pump_report,
                trigger=parse_cron(schedule),
                args=[symbols, top_n, telegram.notify],
            )

    # Volume scanner: cron
    if config["volume"]["enabled"]:
        schedule = config["volume"]["schedule"]
        print(f'Volume scanner: cron "{schedule}"')
        scheduler.add_job(
            run_volume_scan,
            trigger=parse_cron(schedule),
            args=[symbols, config["volume"], telegram.notify],
        )

    # Signal scanner: polling loop (every 5 min)
    if config["signals"]["enabled"]:
        poll_sec = config["signals"]["pollIntervalSeconds"]
        print(f"Signal scanner: polling every {poll_sec}s (interval: {config['signals']['interval']})")
        asyncio.create_task(signal_loop(symbols, config["signals"]))

    scheduler.start()

    await telegram.notify(
        f"✅ *Crypto Scanner started*\n"
        f"Tracking *{len(symbols)}* {quote} pairs\n"
        f"Pump: {'✓' if config['pump']['enabled'] else '✗'} | "
        f"Volume: {'✓' if config['volume']['enabled'] else '✗'} | "
        f"Signals: {'✓' if config['signals']['enabled'] else '✗'}"
    )

    print("Crypto Scanner running. Press Ctrl+C to stop.")

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown()
        await close_client()


if __name__ == "__main__":
    asyncio.run(main())
