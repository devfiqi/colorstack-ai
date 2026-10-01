import asyncio
import logging
from pathlib import Path

from colorstack_ai.config import load_environment
from colorstack_ai.discord.client import DiscordIngestionClient
from colorstack_ai.ingestion.store import JsonlMessageStore


async def main() -> None:
    environment = load_environment()
    store = await JsonlMessageStore(
        Path.cwd() / "data" / "discord-messages.jsonl"
    ).open()
    client = DiscordIngestionClient(store)

    try:
        async with client:
            await client.start(environment.discord_token.get_secret_value())
    finally:
        await store.close()


def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception:
        logging.getLogger(__name__).exception("Fatal ingestion error")
        raise SystemExit(1) from None
