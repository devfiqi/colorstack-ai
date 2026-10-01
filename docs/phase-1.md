# Phase 1: Discord ingestion

Phase 1 establishes a reliable, AI-free ingestion layer. It reads Discord,
normalizes message records, passes them through the storage abstraction, and
stays connected for live changes.

## Behavior

- Validates `DISCORD_TOKEN` before connecting.
- Detects every guild available to the bot.
- Finds readable text and announcement channels.
- Discovers active, public archived, and accessible private archived threads.
- Reads all available history through `discord.py` pagination.
- Preserves human and bot messages.
- Continues when an individual channel or thread cannot be read.
- Handles live creates, raw edits, deletions, and bulk deletions.
- Avoids duplicate historical inserts across restarts.

## Discord configuration

Required gateway intents:

- Guilds
- Guild Messages
- Message Content
- Server Members

Required channel permissions:

- View Channel
- Read Message History

Private archived thread coverage depends on membership or `Manage Threads`.

## Local operation

Install and run from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
alembic upgrade head
python -m colorstack_ai
```

Add the token and local PostgreSQL URL to `.env` without committing or sharing
them.

Successful startup identifies the bot and guilds, reports per-channel backfill
progress, prints final totals, and then logs that it is listening for changes.

## Verification

- Confirm message rows appear in PostgreSQL.
- Restart after a completed backfill; the message row count should not double.
- Create, edit, and delete a test message in an accessible channel.
- Confirm the same row is updated and then marked deleted.
- Run `python -m unittest discover -s tests -v`.

## Limitations

- Discord cannot return already-deleted or inaccessible history.
- Reaction counts are snapshots; reaction-only changes are not live events.
- Display names may be absent when Discord does not provide member data.
- Persistence details are documented separately in
  [Phase 2](phase-2.md).
- No AI extraction, organizational memory, reporting, API, or dashboard exists
  in this phase.
