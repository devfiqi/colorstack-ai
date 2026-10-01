# ColorStack AI — Phase 1 Discord ingestion

This project connects a Discord bot, discovers readable server channels and
threads, backfills available message history, and records live message creates,
edits, and deletions. It intentionally contains no AI or Phase 2 persistence.

## Prerequisites

- Node.js 20 or newer
- A Discord bot installed in the target server
- The bot token from the Discord Developer Portal

## Setup

1. Install dependencies:

   ```bash
   npm install
   ```

2. Create the local environment file:

   ```bash
   cp .env.example .env
   ```

3. Put the bot token in `.env`:

   ```env
   DISCORD_TOKEN=your-token-here
   ```

Never commit `.env` or share the bot token.

## Discord configuration

Enable these gateway intents on the application's **Bot** page:

- Message Content Intent
- Server Members Intent

The client also uses the non-privileged Guilds and Guild Messages intents.

For every channel that should be ingested, the bot role needs:

- View Channel
- Read Message History

Private threads are only discoverable when Discord allows the bot to access
them (for example, when the bot is a thread member or has suitable thread
permissions). Category and channel overrides can deny access even when the bot
role has server-wide permissions.

## Run

Development (automatically restarts after source changes):

```bash
npm run dev
```

Production-style:

```bash
npm run build
npm start
```

Other useful command:

```bash
npm run typecheck
```

## What Phase 1 does

- Validates `DISCORD_TOKEN` before connecting.
- Detects every guild the bot has joined.
- Discovers readable text/announcement channels and active or archived threads.
- Fetches history in 100-message pages until Discord returns no older messages.
- Preserves human and bot messages.
- Normalizes authors, display names, timestamps, replies, attachments, and
  currently visible reaction counts.
- Avoids inserting a known message twice during backfill, including on later
  runs against the same local output.
- Continues when a channel or thread is inaccessible.
- Records live creates, edits, and deletions through the same store boundary.

Records are appended to `data/discord-messages.jsonl`. Each line is either an
`upsert` containing a normalized message snapshot or a `delete` tombstone.
Edits intentionally append a newer snapshot rather than rewriting history.
The `MessageStore` interface is the replacement point for PostgreSQL in a later
phase.

## Verify historical backfill

1. Run `npm run dev`.
2. Confirm the log identifies the bot account and expected server.
3. Compare the discovered channel/thread count with channels visible to the bot.
4. Watch each channel's fetched count increase and finish.
5. Confirm `data/discord-messages.jsonl` exists and contains one JSON object per
   line.
6. Stop and restart the process. Existing historical messages should report as
   already known (`0 new`) rather than being appended again.

## Verify live ingestion

After the `Listening for new messages...` log:

1. Send a message in a readable channel and look for `Ingested new message`.
2. Edit it and look for `Ingested edit`.
3. Delete it and look for `Recorded deletion`.
4. Inspect the final lines of `data/discord-messages.jsonl` for the matching
   upsert and delete records.

## Known limitations

- Discord only exposes retained messages that the bot can currently access;
  already-deleted messages and inaccessible channel history cannot be recovered.
- Archived private-thread discovery depends on Discord permissions and thread
  membership. Failures are logged and do not stop the run.
- Reaction metadata is a snapshot taken when a message is fetched or updated.
  Reaction-only changes are not live events in Phase 1.
- Display names can be `null` when Discord does not provide a guild member with
  the message.
- The JSONL store is for local verification, not concurrent multi-process use,
  querying, compaction, or production durability.
- Large servers may take substantial time to backfill due to Discord rate
  limits. `discord.js` queues requests and respects those limits automatically.
