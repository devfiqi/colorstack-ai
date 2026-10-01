import type { Message } from "discord.js";
import type { NormalizedDiscordMessage } from "./types.js";

export function normalizeMessage(message: Message): NormalizedDiscordMessage {
  const channelName =
    "name" in message.channel && typeof message.channel.name === "string"
      ? message.channel.name
      : null;

  return {
    id: message.id,
    guildId: message.guildId,
    channelId: message.channelId,
    channelName,
    threadId: message.channel.isThread() ? message.channelId : null,
    authorId: message.author.id,
    username: message.author.username,
    displayName: message.member?.displayName ?? null,
    content: message.content,
    createdAt: message.createdAt,
    editedAt: message.editedAt,
    replyToMessageId: message.reference?.messageId ?? null,
    attachments: message.attachments.map((attachment) => ({
      id: attachment.id,
      name: attachment.name,
      url: attachment.url,
      contentType: attachment.contentType,
      size: attachment.size,
    })),
    reactions: message.reactions.cache.map((reaction) => ({
      emoji:
        reaction.emoji.id === null
          ? (reaction.emoji.name ?? "unknown")
          : `${reaction.emoji.name ?? "emoji"}:${reaction.emoji.id}`,
      count: reaction.count,
    })),
  };
}
