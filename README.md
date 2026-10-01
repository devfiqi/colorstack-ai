# ColorStack AI

ColorStack AI is an internal AI chief-of-staff system for the University of
Minnesota ColorStack Discord server. It turns conversations into structured
organizational context and proactive executive updates.

## Current status

Discord ingestion and local PostgreSQL persistence are implemented. The Python
service discovers accessible channels and threads, backfills message history,
normalizes message metadata, and records live creates, edits, and deletions.

AI extraction, organizational memory, reasoning, and executive reports are
planned but not implemented.

## System direction

```text
Discord
  ↓
Ingestion
  ↓
Raw message storage
  ↓
Local LLM extraction
  ↓
Structured organizational state
  ↓
Reasoning model
  ↓
Daily executive brief / on-demand answers
```

## Local setup

Requirements: Python 3.12+, Homebrew, and the configured Discord bot.

```bash
brew install postgresql@17
brew services start postgresql@17
createdb colorstack_ai

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
```

Set `DISCORD_TOKEN` in `.env`; the default local database URL is:

```env
DATABASE_URL=postgresql+psycopg://localhost/colorstack_ai
```

Apply and inspect migrations:

```bash
alembic upgrade head
alembic current
alembic check
```

Run the bot:

```bash
python -m colorstack_ai
```

## Verification queries

```bash
psql colorstack_ai
```

```sql
SELECT COUNT(*) FROM messages;
SELECT COUNT(*) FROM attachments;
SELECT COUNT(*) FROM reactions;
SELECT COUNT(*) FROM messages WHERE is_deleted;
SELECT id, channel_name, edited_at
FROM messages
WHERE edited_at IS NOT NULL
ORDER BY edited_at DESC
LIMIT 10;
```

## Documentation

- [Architecture](ARCHITECTURE.md)
- [Roadmap](ROADMAP.md)
- [Security](SECURITY.md)
- [Phase 1 ingestion](docs/phase-1.md)
- [Phase 2 PostgreSQL persistence](docs/phase-2.md)
- [Data model](docs/data-model.md)
- [Technical decisions](docs/decisions.md)

Discord content and credentials remain local. They are excluded from Git and
are not sent to an AI provider or externally hosted database.
