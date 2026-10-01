import logging
from dataclasses import dataclass

from colorstack_ai.discord.channels import ReadableMessageChannel
from colorstack_ai.ingestion.normalize import normalize_message
from colorstack_ai.ingestion.store import MessageStore

logger = logging.getLogger(__name__)


@dataclass
class BackfillResult:
    fetched: int = 0
    inserted: int = 0
    failed_channels: int = 0


async def _backfill_channel(
    channel: ReadableMessageChannel,
    store: MessageStore,
) -> tuple[int, int]:
    fetched = 0
    inserted = 0
    logger.info("Backfilling #%s (%s)...", channel.name, channel.id)

    async for message in channel.history(limit=None, oldest_first=False):
        fetched += 1
        if await store.insert(normalize_message(message)):
            inserted += 1

        if fetched % 100 == 0:
            logger.info(
                "Fetched %s messages from #%s (%s new)",
                f"{fetched:,}",
                channel.name,
                f"{inserted:,}",
            )

    logger.info(
        "Finished #%s: %s fetched, %s new",
        channel.name,
        f"{fetched:,}",
        f"{inserted:,}",
    )
    return fetched, inserted


async def backfill_channels(
    channels: list[ReadableMessageChannel],
    store: MessageStore,
) -> BackfillResult:
    result = BackfillResult()

    for channel in channels:
        try:
            fetched, inserted = await _backfill_channel(channel, store)
            result.fetched += fetched
            result.inserted += inserted
        except Exception:
            result.failed_channels += 1
            logger.exception(
                "Skipping inaccessible channel #%s (%s)",
                channel.name,
                channel.id,
            )

    return result
