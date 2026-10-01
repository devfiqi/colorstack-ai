from typing import Any

import discord

from colorstack_ai.briefing.formatter import split_discord_messages
from colorstack_ai.briefing.models import BriefDeliveryResult


class BriefDeliveryError(RuntimeError):
    pass


class DiscordBriefDelivery:
    def __init__(self, client: discord.Client, channel_id: str) -> None:
        self._client = client
        self._channel_id = channel_id

    async def send(self, rendered_text: str) -> BriefDeliveryResult:
        channel_id = int(self._channel_id)
        resolved = self._client.get_channel(channel_id)
        if resolved is None:
            try:
                resolved = await self._client.fetch_channel(channel_id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as error:
                raise BriefDeliveryError(
                    f"Leadership channel {self._channel_id} is unavailable."
                ) from error
        if isinstance(resolved, discord.Thread) or not hasattr(resolved, "guild"):
            raise BriefDeliveryError(
                "DAILY_BRIEF_CHANNEL_ID must identify a guild text channel."
            )
        channel: Any = resolved
        guild = channel.guild
        member = guild.me
        if member is None:
            raise BriefDeliveryError("The bot is not a member of the channel guild.")
        permissions = channel.permissions_for(member)
        if not permissions.view_channel:
            raise BriefDeliveryError("The bot cannot view the leadership channel.")
        if not permissions.send_messages:
            raise BriefDeliveryError("The bot cannot send to the leadership channel.")

        message_ids: list[str] = []
        for chunk in split_discord_messages(rendered_text):
            try:
                message: Any = await channel.send(chunk)
            except (discord.Forbidden, discord.HTTPException) as error:
                raise BriefDeliveryError(
                    "Discord rejected daily brief delivery."
                ) from error
            message_ids.append(str(message.id))
        return BriefDeliveryResult(
            channel_id=self._channel_id,
            message_ids=message_ids,
        )
