import logging
from typing import Protocol

import discord

from colorstack_ai.discord.backfill import backfill_channels
from colorstack_ai.discord.channels import (
    ReadableMessageChannel,
    find_readable_message_channels,
)
from colorstack_ai.discord.listeners import (
    ingest_message_create,
    ingest_raw_bulk_message_delete,
    ingest_raw_message_delete,
    ingest_raw_message_edit,
)
from colorstack_ai.ingestion.store import MessageStore

logger = logging.getLogger(__name__)


class BriefScheduler(Protocol):
    def start(self) -> None: ...
    def shutdown(self) -> None: ...


class IntelligencePipeline(Protocol):
    def start(self) -> None: ...
    async def shutdown(self) -> None: ...


def create_intents() -> discord.Intents:
    intents = discord.Intents.none()
    intents.guilds = True
    intents.guild_messages = True
    intents.members = True
    intents.message_content = True
    return intents


class DiscordIngestionClient(discord.Client):
    def __init__(self, store: MessageStore) -> None:
        super().__init__(intents=create_intents())
        self._store = store
        self._initialization_started = False
        self._brief_scheduler: BriefScheduler | None = None
        self._intelligence_pipeline: IntelligencePipeline | None = None

    def set_brief_scheduler(self, scheduler: BriefScheduler) -> None:
        self._brief_scheduler = scheduler

    def set_intelligence_pipeline(self, pipeline: IntelligencePipeline) -> None:
        self._intelligence_pipeline = pipeline

    async def on_ready(self) -> None:
        if self._initialization_started:
            logger.info("Discord connection resumed as %s", self.user)
            return

        self._initialization_started = True
        logger.info("Connected as %s", self.user)

        if not self.guilds:
            logger.error(
                "The bot is not connected to any guilds. "
                "Confirm it was added to the server."
            )
            await self.close()
            return

        logger.info(
            "Detected %d guild%s: %s",
            len(self.guilds),
            "" if len(self.guilds) == 1 else "s",
            ", ".join(f"{guild.name} ({guild.id})" for guild in self.guilds),
        )

        channels: list[ReadableMessageChannel] = []
        for guild in self.guilds:
            try:
                guild_channels = await find_readable_message_channels(guild)
                channels.extend(guild_channels)
                logger.info(
                    "Found %d readable message channels and threads in %s",
                    len(guild_channels),
                    guild.name,
                )
            except Exception:
                logger.exception("Could not enumerate channels in %s", guild.name)

        result = await backfill_channels(channels, self._store)
        logger.info("Historical backfill complete")
        logger.info("Total fetched: %s", f"{result.fetched:,}")
        logger.info("Newly stored: %s", f"{result.inserted:,}")
        if result.failed_channels:
            logger.warning("Skipped channels: %d", result.failed_channels)
        if self._intelligence_pipeline is not None:
            self._intelligence_pipeline.start()
        if self._brief_scheduler is not None:
            self._brief_scheduler.start()
        logger.info("Listening for new messages, edits, and deletions...")

    async def close(self) -> None:
        if self._brief_scheduler is not None:
            self._brief_scheduler.shutdown()
        if self._intelligence_pipeline is not None:
            await self._intelligence_pipeline.shutdown()
        await super().close()

    async def on_message(self, message: discord.Message) -> None:
        await ingest_message_create(self._store, message)

    async def on_raw_message_edit(
        self,
        payload: discord.RawMessageUpdateEvent,
    ) -> None:
        await ingest_raw_message_edit(self, self._store, payload)

    async def on_raw_message_delete(
        self,
        payload: discord.RawMessageDeleteEvent,
    ) -> None:
        await ingest_raw_message_delete(self._store, payload)

    async def on_raw_bulk_message_delete(
        self,
        payload: discord.RawBulkMessageDeleteEvent,
    ) -> None:
        await ingest_raw_bulk_message_delete(self._store, payload)
