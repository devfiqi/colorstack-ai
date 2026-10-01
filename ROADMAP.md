# Roadmap

## Phase 1 — Discord ingestion

Status: implemented.

- Connect with validated credentials and required intents.
- Discover readable guild channels and accessible threads.
- Backfill complete available message history.
- Normalize messages, replies, attachments, and reactions.
- Deduplicate historical records across restarts.
- Record live creates, edits, individual deletions, and bulk deletions.
- Keep persistence behind a replaceable store interface.

## Phase 2 — Durable structured storage

Status: implemented and manually verified.

- PostgreSQL is the durable, queryable raw archive.
- SQLAlchemy models and Alembic migrations define the schema.
- Backfills are resumable and idempotent by Discord message ID.
- Edits update existing rows; deletes preserve content through soft deletion.
- Attachments and reaction snapshots use related tables.
- Integration tests cover duplicates, edits, related records, and deletions.
- Discord content remains local.

Deferred operational work:

- Define backup and restore procedures.
- Define retention and relevance rules before discarding any raw data.
- Evaluate batching only if message volume makes per-message transactions slow.

## Phase 3 — Local extraction

- Evaluate a local model against representative Discord messages.
- Extract tasks, owners, deadlines, decisions, blockers, and event updates.
- Record confidence and source message IDs for every extracted fact.
- Add replayable extraction jobs and human-correction paths.

## Phase 4 — Organizational memory

- Model events, people, tasks, decisions, and status changes.
- Reconcile new facts with current event state.
- Preserve provenance and conflicting information.
- Support targeted queries without rereading the full message archive.

## Phase 5 — Reasoning and reporting

- Answer leadership questions from structured, source-linked context.
- Generate daily executive briefs.
- Surface stale tasks, unresolved blockers, and approaching deadlines.
- Add approval and delivery controls before reports reach Discord users.

## Not planned during Phase 1

AI extraction, embeddings, vector search, dashboards, scheduled reports, and
external data sharing are intentionally outside the current implementation.
