import {
  Client,
  GatewayIntentBits,
  Partials,
} from "discord.js";

export function createDiscordClient(): Client {
  return new Client({
    intents: [
      GatewayIntentBits.Guilds,
      GatewayIntentBits.GuildMessages,
      GatewayIntentBits.GuildMembers,
      GatewayIntentBits.MessageContent,
    ],
    partials: [Partials.Channel, Partials.Message, Partials.Reaction],
  });
}

export function waitUntilReady(client: Client): Promise<Client<true>> {
  if (client.isReady()) {
    return Promise.resolve(client);
  }

  return new Promise((resolve) => {
    client.once("ready", (readyClient) => resolve(readyClient));
  });
}
