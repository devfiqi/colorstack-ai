# ColorStack AI — Phase 1 Discord ingestion

Python service that discovers readable Discord channels and threads, backfills
available message history, and records live creates, edits, and deletions. It
intentionally contains no AI or Phase 2 database functionality.

## Prerequisites

- Python 3.12 or newer
- A Discord bot installed in the target server
- The bot token from the Discord Developer Portal

## Setup

Create a virtual environment and install the project:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Create the local environment file:

```bash
cp .env.example .env
```

Add the bot token:

```env
DISCORD_TOKEN=your-token-here
```

Never commit `.env` or share the bot token.

## Discord configuration

Enable these gateway intents on the application's **Bot** page:

- Message Content Intent
- Server Members Intent

The client also enables the non-privileged Guilds and Guild Messages intents.
For every channel that should be ingested, the bot role needs:

- View Channel
- Read Message History

Private threads are only discoverable when the bot is a member or has
`Manage Threads`. Category and channel overrides can deny access even when the
bot role has server-wide permissions.

## Run

With the virtual environment active:

```bash
python -m colorstack_ai
```

The installed console command is equivalent:

```bash
colorstack-ai
```

Run the local tests with:

```bash
python -m unittest discover -s tests -v
```

## What Phase 1 does

- Validates `DISCORD_TOKEN` before connecting.
- Detects every guild the bot has joined.
- Discovers readable text/announcement channels and accessible active or
  archived threads.
- Uses `discord.py` history iteration, which transparently paginates until no
  older messages remain and respects Discord rate limits.
- Preserves human and bot messages.
- Normalizes authors, display names, timestamps, replies, attachments, and
  currently visible reaction counts with Pydantic models.
- Avoids inserting a known message twice during backfill, including after
  restarts.
- Continues when an individual channel or thread cannot be read.
- Records live creates, edits, individual deletions, and bulk deletions.

Records are appended to `data/discord-messages.jsonl`. Each line is either an
`upsert` containing a normalized message snapshot or a `delete` tombstone.
Edits append a newer snapshot instead of rewriting history. `MessageStore` is
the replacement boundary for PostgreSQL in Phase 2.

## Verify historical backfill

1. Run `python -m colorstack_ai`.
2. Confirm the log identifies the expected bot and guild.
3. Compare the discovered channel/thread count with what the bot can see.
4. Watch each channel's fetched count increase and finish.
5. Confirm `data/discord-messages.jsonl` contains one JSON object per line.
6. Restart the process. Existing history should report `0 new` instead of being
   appended again.

## Verify live ingestion

After the `Listening for new messages...` log:

1. Send a message and look for `Ingested new message`.
2. Edit it and look for `Ingested edit`.
3. Delete it and look for `Recorded deletion`.
4. Inspect the final JSONL lines for the corresponding upsert and tombstone.

## Known limitations

- Discord cannot return already-deleted messages or history hidden from the bot.
- Archived private-thread discovery depends on permissions and membership.
- Reaction metadata is a fetch-time snapshot; reaction-only changes are not
  live events in Phase 1.
- Display names can be `null` when Discord does not provide a guild member.
- The JSONL store is for one local process, not production concurrency,
  querying, compaction, or database-grade durability.
- Large servers can take substantial time to backfill due to Discord rate
  limits.
