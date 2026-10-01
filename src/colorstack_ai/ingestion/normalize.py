import discord

from colorstack_ai.ingestion.models import (
    NormalizedAttachment,
    NormalizedDiscordMessage,
    NormalizedReaction,
)


def normalize_message(message: discord.Message) -> NormalizedDiscordMessage:
    channel_name = getattr(message.channel, "name", None)
    display_name = (
        message.author.display_name
        if isinstance(message.author, discord.Member)
        else None
    )

    return NormalizedDiscordMessage(
        id=str(message.id),
        guild_id=str(message.guild.id) if message.guild else None,
        channel_id=str(message.channel.id),
        channel_name=channel_name,
        thread_id=(
            str(message.channel.id)
            if isinstance(message.channel, discord.Thread)
            else None
        ),
        author_id=str(message.author.id),
        username=message.author.name,
        display_name=display_name,
        content=message.content,
        created_at=message.created_at,
        edited_at=message.edited_at,
        reply_to_message_id=(
            str(message.reference.message_id)
            if message.reference and message.reference.message_id
            else None
        ),
        attachments=[
            NormalizedAttachment(
                id=str(attachment.id),
                name=attachment.filename,
                url=attachment.url,
                content_type=attachment.content_type,
                size=attachment.size,
            )
            for attachment in message.attachments
        ],
        reactions=[
            NormalizedReaction(emoji=str(reaction.emoji), count=reaction.count)
            for reaction in message.reactions
        ],
    )
