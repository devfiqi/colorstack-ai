import logging
from datetime import UTC, datetime
from typing import Protocol, cast

import discord

from colorstack_ai.ingestion.models import DeletedDiscordMessage
from colorstack_ai.ingestion.normalize import normalize_message
from colorstack_ai.ingestion.store import MessageStore

logger = logging.getLogger(__name__)


class MessageFetchChannel(Protocol):
    async def fetch_message(self, message_id: int, /) -> discord.Message: ...


async def ingest_message_create(
    store: MessageStore,
    message: discord.Message,
) -> None:
    if message.guild is None:
        return

    await store.upsert(normalize_message(message))
    logger.info("Ingested new message %s", message.id)


async def ingest_raw_message_edit(
    client: discord.Client,
    store: MessageStore,
    payload: discord.RawMessageUpdateEvent,
) -> None:
    if payload.guild_id is None:
        return

    try:
        channel = client.get_channel(payload.channel_id)
        if channel is None:
            channel = await client.fetch_channel(payload.channel_id)
        fetch_channel = cast(MessageFetchChannel, channel)
        message = await fetch_channel.fetch_message(payload.message_id)
        await store.upsert(normalize_message(message))
        logger.info("Ingested edit to message %s", message.id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException) as error:
        logger.warning(
            "Could not ingest edit to message %s: %s",
            payload.message_id,
            error,
        )


async def ingest_raw_message_delete(
    store: MessageStore,
    payload: discord.RawMessageDeleteEvent,
) -> None:
    if payload.guild_id is None:
        return

    await store.mark_deleted(
        DeletedDiscordMessage(
            id=str(payload.message_id),
            guild_id=str(payload.guild_id),
            channel_id=str(payload.channel_id),
            deleted_at=datetime.now(UTC),
        )
    )
    logger.info("Recorded deletion of message %s", payload.message_id)


async def ingest_raw_bulk_message_delete(
    store: MessageStore,
    payload: discord.RawBulkMessageDeleteEvent,
) -> None:
    if payload.guild_id is None:
        return

    deleted_at = datetime.now(UTC)
    for message_id in payload.message_ids:
        await store.mark_deleted(
            DeletedDiscordMessage(
                id=str(message_id),
                guild_id=str(payload.guild_id),
                channel_id=str(payload.channel_id),
                deleted_at=deleted_at,
            )
        )

    logger.info("Recorded bulk deletion of %d messages", len(payload.message_ids))
