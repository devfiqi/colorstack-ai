import type { Snowflake } from "discord.js";
import { normalizeMessage } from "../ingestion/normalizeMessage.js";
import type { MessageStore } from "../ingestion/store.js";
import type { ReadableMessageChannel } from "./channels.js";

export type BackfillResult = {
  fetched: number;
  inserted: number;
  failedChannels: number;
};

async function backfillChannel(
  channel: ReadableMessageChannel,
  store: MessageStore,
): Promise<{ fetched: number; inserted: number }> {
  let before: Snowflake | undefined;
  let fetched = 0;
  let inserted = 0;

  console.log(`\nBackfilling #${channel.name} (${channel.id})...`);

  while (true) {
    const messages = await channel.messages.fetch({ limit: 100, before });
    if (messages.size === 0) break;

    fetched += messages.size;
    for (const message of messages.values()) {
      if (await store.insert(normalizeMessage(message))) {
        inserted += 1;
      }
    }

    console.log(
      `Fetched ${fetched.toLocaleString()} messages (${inserted.toLocaleString()} new)`,
    );

    before = messages.last()?.id;
    if (!before) break;
  }

  console.log(
    `Finished #${channel.name}: ${fetched.toLocaleString()} fetched, ${inserted.toLocaleString()} new`,
  );
  return { fetched, inserted };
}

export async function backfillChannels(
  channels: ReadableMessageChannel[],
  store: MessageStore,
): Promise<BackfillResult> {
  const result: BackfillResult = {
    fetched: 0,
    inserted: 0,
    failedChannels: 0,
  };

  for (const channel of channels) {
    try {
      const channelResult = await backfillChannel(channel, store);
      result.fetched += channelResult.fetched;
      result.inserted += channelResult.inserted;
    } catch (error) {
      result.failedChannels += 1;
      console.error(
        `Skipping inaccessible channel #${channel.name} (${channel.id}):`,
        error,
      );
    }
  }

  return result;
}
