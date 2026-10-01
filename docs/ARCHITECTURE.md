# Architecture

ColorStack AI converts Discord activity into durable organizational context.
Ingestion, the local PostgreSQL archive, local fact extraction, and
organizational state reconciliation are implemented.

## System flow

```text
Discord
  ↓
Ingestion                         implemented
  ↓
Raw PostgreSQL archive           implemented locally
  ↓
Relevance filter                 implemented
  ↓
Local LLM fact extraction        implemented
  ↓
Structured organizational state implemented
  ↓
Reasoning model                  planned
  ↓
Executive briefs and answers     planned
```

## Implemented components

- `config.py` loads `.env` and validates the Discord token.
- `discord/client.py` owns the Discord connection and ingestion lifecycle.
- `discord/channels.py` discovers readable channels and accessible threads.
- `discord/backfill.py` reads complete available history and reports progress.
- `discord/listeners.py` handles live creates, edits, and deletions.
- `ingestion/normalize.py` converts Discord objects into internal models.
- `ingestion/models.py` defines the normalized Pydantic records.
- `ingestion/store.py` defines the persistence boundary.
- `ingestion/postgres_store.py` implements transactional PostgreSQL persistence.
- `db/models.py` defines the SQLAlchemy archive schema.
- `db/session.py` owns the async engine and session factory.
- `alembic/` contains the versioned database migrations.
- `extraction/relevance.py` performs conservative deterministic filtering.
- `extraction/context.py` builds bounded reply and nearby-message context.
- `extraction/ollama.py` validates and calls a local Ollama model.
- `extraction/prompt.py` contains the versioned extraction instructions.
- `extraction/processor.py` coordinates filtering, extraction, and progress.
- `extraction/repository.py` persists runs, states, and append-only facts.
- `extract/` provides backfill, new-message, and retry CLI modes.
- `state/resolution.py` conservatively resolves canonical events and tasks.
- `state/policy.py` contains deterministic precedence and lifecycle rules.
- `state/repository.py` persists current values, audit history, and unresolved
  facts transactionally.
- `state/processor.py` coordinates idempotent reconciliation and rebuilds.
- `state/ambiguity.py` validates optional local-model interpretations.
- `state/` provides reconcile-new, retry-unresolved, and rebuild CLI modes.

## Runtime flow

1. Validate configuration and open the message store.
2. Connect with guild, message, member, and message-content intents.
3. Discover readable text channels and active or archived threads.
4. Backfill each channel independently; a channel failure does not stop others.
5. Upsert messages and related snapshots by Discord message ID.
6. Continue processing live creates, raw edits, and deletion events.

The event handlers are active during backfill, preventing a gap between history
collection and live ingestion.

## Storage boundary

`MessageStore` isolates Discord ingestion from persistence. Phase 1 uses the
append-only JSONL verification store; Phase 2 makes `PostgresMessageStore` the
runtime default without changing discovery, normalization, or listeners.

PostgreSQL is the durable raw source of truth. Message IDs are primary keys,
edits update the existing row and related snapshots, and deletions set a flag
and timestamp rather than removing data. Attachments and reactions are separate
tables tied to messages with cascading foreign keys.

## Extraction boundary

Phase 3 records facts attributable to individual source messages and extraction
versions. It deliberately preserves competing facts and does not decide which is
currently true. Low-relevance messages remain in the raw archive and receive a
processing-state record rather than being deleted.

## State boundary

Phase 4 treats extracted facts as immutable evidence and current state as a
rebuildable projection. Every applied value points to a fact and source message;
each transition is recorded in `state_changes`. Ambiguous entity matches or
unsafe updates are retained in processing and unresolved records instead of
being guessed.

Entity resolution is guild-scoped and conservative. Mutable values use an
extensible field/value representation over canonical event and task identities.
Deterministic policy controls precedence; Ollama can only return a validated
proposal and never writes state directly.

## Planned layers

Phase 5 will add event playbooks and higher-level reasoning over the structured,
source-linked state.
