# Architecture

ColorStack AI converts Discord activity into durable organizational context.
Only the ingestion and local raw-storage layers are implemented today.

## System flow

```text
Discord
  ↓
Ingestion                         implemented
  ↓
Raw message storage              implemented locally
  ↓
Local LLM extraction             planned
  ↓
Structured organizational state planned
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
- `ingestion/store.py` defines the persistence boundary and local JSONL store.

## Runtime flow

1. Validate configuration and open the message store.
2. Connect with guild, message, member, and message-content intents.
3. Discover readable text channels and active or archived threads.
4. Backfill each channel independently; a channel failure does not stop others.
5. Deduplicate historical messages by Discord message ID.
6. Continue processing live creates, raw edits, and deletion events.

The event handlers are active during backfill, preventing a gap between history
collection and live ingestion.

## Storage boundary

`MessageStore` isolates Discord ingestion from persistence. Phase 1 uses the
append-only `data/discord-messages.jsonl` file. A future database implementation
can replace it without changing channel discovery, normalization, or listeners.

Raw messages remain the source of truth. Updates append a new snapshot, and
deletions append tombstones rather than removing prior records.

## Planned layers

The extraction layer will turn raw conversations into tasks, owners, deadlines,
decisions, blockers, and event updates. Organizational memory will reconcile
those facts into current event state while retaining links to source messages.
A reasoning layer will use that state for on-demand answers and executive
briefs.
