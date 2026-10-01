# ColorStack AI

ColorStack AI is an internal AI chief-of-staff system for the University of
Minnesota ColorStack Discord server. It turns conversations into structured
organizational context and proactive executive updates.

## Current status

Discord ingestion, local PostgreSQL persistence, local fact extraction, and
versioned organizational-state reconciliation are implemented. Reasoning,
event playbooks, and executive reports are not implemented.

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

Configure local extraction:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=your-installed-model
EXTRACTION_VERSION=v2
```

```bash
ollama list
python -m colorstack_ai.extract backfill --limit 100
python -m colorstack_ai.extract new
python -m colorstack_ai.extract retry-failed
```

Reconcile facts into current state:

```bash
python -m colorstack_ai.state reconcile-new
python -m colorstack_ai.state retry-unresolved
python -m colorstack_ai.state rebuild
```

Add `--resolve-ambiguous` to use the configured local Ollama model only for
facts that deterministic rules cannot classify safely.

## Verification queries

```bash
psql colorstack_ai
```

```sql
SELECT COUNT(*) FROM messages;
SELECT COUNT(*) FROM attachments;
SELECT COUNT(*) FROM reactions;
SELECT COUNT(*) FROM extracted_facts;
SELECT COUNT(*) FROM current_state_values;
SELECT COUNT(*) FROM state_changes;
SELECT COUNT(*) FROM unresolved_facts WHERE status = 'unresolved';
SELECT COUNT(*) FROM messages WHERE is_deleted;
SELECT id, channel_name, edited_at
FROM messages
WHERE edited_at IS NOT NULL
ORDER BY edited_at DESC
LIMIT 10;
```

## Documentation

- [Agent instructions](docs/AGENTS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [Security](docs/SECURITY.md)
- [Phase 1 ingestion](docs/phase-1.md)
- [Phase 2 PostgreSQL persistence](docs/phase-2.md)
- [Phase 3 local extraction](docs/phase-3.md)
- [Phase 4 organizational state](docs/phase-4.md)
- [Data model](docs/data-model.md)
- [Technical decisions](docs/decisions.md)
- [Bot communication policy](docs/BOT_PERMISSIONS.md)

Discord content and credentials remain local. They are excluded from Git and
are not sent to an AI provider or externally hosted database.
