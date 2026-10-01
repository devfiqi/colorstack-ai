import { resolve } from "node:path";
import { loadEnvironment } from "./config/env.js";
import { backfillChannels } from "./discord/backfill.js";
import {
  findReadableMessageChannels,
  type ReadableMessageChannel,
} from "./discord/channels.js";
import { createDiscordClient, waitUntilReady } from "./discord/client.js";
import { registerMessageListeners } from "./discord/listeners.js";
import { JsonlMessageStore } from "./ingestion/store.js";

async function main(): Promise<void> {
  const environment = loadEnvironment();
  const store = await JsonlMessageStore.create(
    resolve(process.cwd(), "data", "discord-messages.jsonl"),
  );
  const client = createDiscordClient();

  const shutdown = async (signal: string): Promise<void> => {
    console.log(`\nReceived ${signal}; shutting down...`);
    client.destroy();
    await store.close();
    process.exit(0);
  };

  process.once("SIGINT", () => void shutdown("SIGINT"));
  process.once("SIGTERM", () => void shutdown("SIGTERM"));

  registerMessageListeners(client, store);
  client.on("error", (error) => console.error("Discord client error:", error));

  try {
    await client.login(environment.discordToken);
    const readyClient = await waitUntilReady(client);
    console.log(`Connected as ${readyClient.user.tag}`);

    const guilds = [...readyClient.guilds.cache.values()];
    if (guilds.length === 0) {
      throw new Error(
        "The bot is not connected to any guilds. Confirm it was added to the server.",
      );
    }

    console.log(
      `Detected ${guilds.length} guild${guilds.length === 1 ? "" : "s"}: ${guilds
        .map((guild) => `${guild.name} (${guild.id})`)
        .join(", ")}`,
    );

    const channels: ReadableMessageChannel[] = [];
    for (const guild of guilds) {
      try {
        const guildChannels = await findReadableMessageChannels(guild);
        channels.push(...guildChannels);
        console.log(
          `Found ${guildChannels.length} readable message channels and threads in ${guild.name}`,
        );
      } catch (error) {
        console.error(`Could not enumerate channels in ${guild.name}:`, error);
      }
    }

    const result = await backfillChannels(channels, store);
    console.log("\nHistorical backfill complete");
    console.log(`Total fetched: ${result.fetched.toLocaleString()}`);
    console.log(`Newly stored: ${result.inserted.toLocaleString()}`);
    if (result.failedChannels > 0) {
      console.warn(`Skipped channels: ${result.failedChannels}`);
    }
    console.log("Listening for new messages, edits, and deletions...");
  } catch (error) {
    client.destroy();
    await store.close();
    throw error;
  }
}

main().catch((error) => {
  console.error("Fatal ingestion error:", error);
  process.exitCode = 1;
});
