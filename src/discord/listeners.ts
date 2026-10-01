import type { Client, Message, PartialMessage } from "discord.js";
import { normalizeMessage } from "../ingestion/normalizeMessage.js";
import type { MessageStore } from "../ingestion/store.js";

async function ensureFullMessage(
  message: Message | PartialMessage,
): Promise<Message | null> {
  if (!message.partial) return message;

  try {
    return await message.fetch();
  } catch (error) {
    console.warn(`Could not fetch partial message ${message.id}:`, error);
    return null;
  }
}

export function registerMessageListeners(
  client: Client,
  store: MessageStore,
): void {
  client.on("messageCreate", (message) => {
    void store
      .upsert(normalizeMessage(message))
      .then(() => console.log(`Ingested new message ${message.id}`))
      .catch((error) =>
        console.error(`Failed to ingest new message ${message.id}:`, error),
      );
  });

  client.on("messageUpdate", (_oldMessage, newMessage) => {
    void ensureFullMessage(newMessage)
      .then(async (message) => {
        if (!message) return;
        await store.upsert(normalizeMessage(message));
        console.log(`Ingested edit to message ${message.id}`);
      })
      .catch((error) =>
        console.error(`Failed to ingest message edit ${newMessage.id}:`, error),
      );
  });

  client.on("messageDelete", (message) => {
    void store
      .markDeleted({
        id: message.id,
        guildId: message.guildId,
        channelId: message.channelId,
        deletedAt: new Date(),
      })
      .then(() => console.log(`Recorded deletion of message ${message.id}`))
      .catch((error) =>
        console.error(`Failed to record deletion ${message.id}:`, error),
      );
  });

  client.on("messageDeleteBulk", (messages) => {
    for (const message of messages.values()) {
      void store
        .markDeleted({
          id: message.id,
          guildId: message.guildId,
          channelId: message.channelId,
          deletedAt: new Date(),
        })
        .catch((error) =>
          console.error(`Failed to record bulk deletion ${message.id}:`, error),
        );
    }
    console.log(`Recording bulk deletion of ${messages.size} messages`);
  });
}
