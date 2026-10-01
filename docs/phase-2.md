# Phase 2: PostgreSQL persistence

Phase 2 replaces the runtime JSONL verification store with a durable local
PostgreSQL archive. Discord discovery, normalization, backfill, and listeners
remain unchanged.

## What it adds

- Async SQLAlchemy 2.x sessions using `psycopg`.
- Alembic-managed schema migrations.
- Idempotent message inserts keyed by Discord message ID.
- In-place updates for edits and current attachment/reaction snapshots.
- Soft deletion with a flag and deletion timestamp.
- Connection and schema validation before Discord login.
- Integration tests against a migrated PostgreSQL test database.

PostgreSQL is the default runtime store. The JSONL implementation remains only
as a lightweight development and regression-test backend.

## Schema

- `messages`: normalized message content, Discord identifiers, author snapshot,
  timestamps, reply reference, deletion state, and ingestion timestamps.
- `attachments`: attachment metadata keyed by Discord attachment ID.
- `reactions`: current reaction counts keyed by message and emoji.
- `alembic_version`: the migration revision applied to the database.

See [data-model.md](data-model.md) for field-level details.

## Local setup

```bash
brew install postgresql@17
brew services start postgresql@17
createdb colorstack_ai
```

Configure `.env`:

```env
DATABASE_URL=postgresql+psycopg://localhost/colorstack_ai
```

Do not commit `.env` or add credentials to the repository.

## Migrations

Apply all migrations:

```bash
source .venv/bin/activate
alembic upgrade head
```

Inspect migration state and model drift:

```bash
alembic current
alembic history
alembic check
```

Create future schema revisions only after updating SQLAlchemy models:

```bash
alembic revision --autogenerate -m "describe change"
```

## Run

```bash
source .venv/bin/activate
python -m colorstack_ai
```

The first PostgreSQL run backfills all available Discord history. Later runs
revisit history safely, update changed snapshots, and create no duplicate
message rows.

## Verification

```sql
SELECT COUNT(*) FROM messages;
SELECT COUNT(*) FROM attachments;
SELECT COUNT(*) FROM reactions;
SELECT COUNT(*) FROM messages WHERE is_deleted;

SELECT id, content, edited_at, last_updated_at
FROM messages
WHERE edited_at IS NOT NULL
ORDER BY edited_at DESC
LIMIT 10;
```

Run persistence tests with an isolated migrated database:

```bash
createdb colorstack_ai_test
DATABASE_URL=postgresql+psycopg://localhost/colorstack_ai_test \
  alembic upgrade head
TEST_DATABASE_URL=postgresql+psycopg://localhost/colorstack_ai_test \
  python -m unittest discover -s tests -v
```

## Current limitations

- PostgreSQL runs locally and has no automated backup or restore workflow yet.
- Related records represent the latest attachment and reaction snapshots, not
  a revision history for every edit.
- A delete for a message never observed by this process is logged but cannot
  create a complete message row.
- Storage operations are per message; bulk database writes are not implemented.
- No AI extraction or structured organizational memory is included.
