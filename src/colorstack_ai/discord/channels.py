import logging

import discord

logger = logging.getLogger(__name__)

ReadableMessageChannel = discord.TextChannel | discord.Thread
ThreadParent = discord.TextChannel | discord.ForumChannel


def _can_read(
    guild: discord.Guild,
    channel: discord.abc.GuildChannel | discord.Thread,
) -> bool:
    member = guild.me
    if member is None:
        return False

    permissions = channel.permissions_for(member)
    return permissions.view_channel and permissions.read_message_history


async def _add_archived_threads(
    guild: discord.Guild,
    parent: ThreadParent,
    readable: dict[int, ReadableMessageChannel],
) -> None:
    try:
        async for thread in parent.archived_threads(limit=None):
            if _can_read(guild, thread):
                readable[thread.id] = thread
    except (discord.Forbidden, discord.HTTPException) as error:
        logger.warning(
            "Could not fetch public archived threads for #%s: %s",
            parent.name,
            error,
        )

    if not isinstance(parent, discord.TextChannel) or parent.is_news():
        return

    member = guild.me
    manage_threads = bool(
        member and parent.permissions_for(member).manage_threads
    )
    try:
        async for thread in parent.archived_threads(
            private=True,
            joined=not manage_threads,
            limit=None,
        ):
            if _can_read(guild, thread):
                readable[thread.id] = thread
    except (discord.Forbidden, discord.HTTPException) as error:
        logger.warning(
            "Could not fetch private archived threads for #%s: %s",
            parent.name,
            error,
        )


async def find_readable_message_channels(
    guild: discord.Guild,
) -> list[ReadableMessageChannel]:
    channels = await guild.fetch_channels()
    readable: dict[int, ReadableMessageChannel] = {}
    thread_parents: list[ThreadParent] = []

    for channel in channels:
        if isinstance(channel, discord.TextChannel):
            if _can_read(guild, channel):
                readable[channel.id] = channel
                thread_parents.append(channel)
        elif isinstance(channel, discord.ForumChannel) and _can_read(guild, channel):
            thread_parents.append(channel)

    try:
        for thread in await guild.active_threads():
            if _can_read(guild, thread):
                readable[thread.id] = thread
    except (discord.Forbidden, discord.HTTPException) as error:
        logger.warning("Could not fetch active threads in %s: %s", guild.name, error)

    for parent in thread_parents:
        await _add_archived_threads(guild, parent, readable)

    return list(readable.values())
