import "dotenv/config";

export type Environment = {
  discordToken: string;
};

export function loadEnvironment(): Environment {
  const discordToken = process.env.DISCORD_TOKEN?.trim();

  if (!discordToken) {
    throw new Error(
      "Missing required environment variable DISCORD_TOKEN. Copy .env.example to .env and add the bot token.",
    );
  }

  return { discordToken };
}
