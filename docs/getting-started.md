# Getting started

This guide contains the technical setup and command reference for ColorStack
AI. For a short overview, see the [main README](../README.md).

## Requirements

- Python 3.12 or newer
- Homebrew
- PostgreSQL 17
- Ollama with a local model installed
- Bun
- A configured Discord bot

## Install the backend

```bash
brew install postgresql@17
brew services start postgresql@17
createdb colorstack_ai

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
```

Set `DISCORD_TOKEN` in `.env`. The default database URL is:

```env
DATABASE_URL=postgresql+psycopg://localhost/colorstack_ai
```

Apply the database migrations:

```bash
alembic upgrade head
alembic current
alembic check
```

## Configure local AI extraction

Add the Ollama settings to `.env`:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=your-installed-model
EXTRACTION_VERSION=v2
PIPELINE_ENABLED=true
PIPELINE_INTERVAL_SECONDS=60
PIPELINE_BATCH_SIZE=100
PIPELINE_RETRY_EVERY_CYCLES=10
```

Confirm the model is available:

```bash
ollama list
```

## Run the app

Run each service in its own terminal.

Start the Discord ingestion and intelligence worker:

```bash
python -m colorstack_ai
```

Start the API:

```bash
colorstack-api
```

Start the dashboard:

```bash
cd frontend
bun install
bun run dev
```

Open `http://localhost:5173`. The API runs at `http://127.0.0.1:8000`, with
interactive API documentation at `http://127.0.0.1:8000/docs`.

For a persistent macOS setup, see [Local services](local-services.md).

## Maintenance commands

Extract facts from Discord messages:

```bash
python -m colorstack_ai.extract backfill --limit 100
python -m colorstack_ai.extract new
python -m colorstack_ai.extract retry-failed
```

Reconcile facts into the current organizational state:

```bash
python -m colorstack_ai.state reconcile-new
python -m colorstack_ai.state retry-unresolved
python -m colorstack_ai.state rebuild
```

Add `--resolve-ambiguous` to use Ollama when deterministic rules cannot safely
classify a fact.

Seed VP-confirmed events and clearly labeled operating-plan recommendations:

```bash
python -m colorstack_ai.operations
```

The seed is idempotent. It preserves confirmed event dates through a state
rebuild and creates recommended work for each chapter division across the
before, during, and after-event phases. Recommendations do not become confirmed
commitments until their owner, deadline, and applicability are clarified.

Reprocess a bounded historical window with a new extraction version:

```bash
EXTRACTION_VERSION=v3 python -m colorstack_ai.extract backfill \
  --from-date 2026-08-03 --to-date 2026-10-03
python -m colorstack_ai.state reconcile-new
```

Run a smaller event-priority pass for urgent operating work:

```bash
EXTRACTION_VERSION=v4 python -m colorstack_ai.extract backfill \
  --from-date 2026-09-12 --to-date 2026-10-03 --event-priority
```

This pass limits candidates to the confirmed Gen AI, Seagate, SIBAT, Ideathon,
and NSBE terms while keeping local reply and nearby-message context.

Validate playbooks and evaluate event requirements:

```bash
python -m colorstack_ai.playbooks list
python -m colorstack_ai.playbooks validate
python -m colorstack_ai.playbooks sync
python -m colorstack_ai.requirements evaluate-all
python -m colorstack_ai.requirements evaluate-event <event-id>
```

Build context packages:

```bash
python -m colorstack_ai.context event <event-id>
python -m colorstack_ai.context task <task-id>
python -m colorstack_ai.context person <discord-user-id>
python -m colorstack_ai.context org
python -m colorstack_ai.context query "What are we missing for Adobe?"
```

Generate or explicitly deliver the daily brief:

```bash
python -m colorstack_ai.briefing preview
python -m colorstack_ai.briefing generate
python -m colorstack_ai.briefing send
python -m colorstack_ai.briefing schedule
```

`DAILY_BRIEF_ENABLED=true` schedules generation only. The `send` command is the
only command that delivers a brief to Discord and must be run directly by a
person.

## More documentation

- [Project phases](phases.md)
- [Architecture](ARCHITECTURE.md)
- [Data model](data-model.md)
- [Technical decisions](decisions.md)
- [Playbook format](playbook-format.md)
- [Bot communication policy](BOT_PERMISSIONS.md)
