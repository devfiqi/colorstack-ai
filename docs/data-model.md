# Data model

PostgreSQL stores the normalized Phase 1 records. Discord snowflakes are kept as
strings to avoid platform integer assumptions.

## `messages`

- `id`: primary key and Discord message ID.
- `guild_id`: source guild ID.
- `channel_id`, `channel_name`: source channel snapshot.
- `thread_id`: thread ID when the source channel is a thread.
- `author_id`, `username`, `display_name`: author snapshot.
- `content`: raw text available through the Message Content intent.
- `created_at`, `edited_at`: Discord timestamps.
- `reply_to_message_id`: referenced Discord message ID.
- `is_deleted`, `deleted_at`: soft-deletion state.
- `ingested_at`: first database insertion time.
- `last_updated_at`: latest persisted change time.

Indexes support common filters on guild, channel, author, creation time, and
deletion state.

## `attachments`

- `id`: primary key and Discord attachment ID.
- `message_id`: foreign key to `messages.id`.
- `name`: filename supplied by Discord.
- `url`: Discord CDN URL.
- `content_type`: reported media type.
- `size`: size in bytes.

Deleting a message row cascades to its attachments, although normal ingestion
uses soft deletion and does not remove message rows.

## `reactions`

- `message_id`: foreign key to `messages.id`.
- `emoji`: Unicode emoji or custom emoji representation.
- `count`: observed reaction count.

The primary key is `(message_id, emoji)`.

## Persistence semantics

- Backfill inserts a message only when its Discord ID is new.
- Existing messages are compared and updated only when normalized data differs.
- Attachment and reaction sets are replaced only when their snapshots differ.
- Live edits update the same message row.
- Deletes mark the existing row; they never remove raw message content.
- Each message operation is transactional across the message and related rows.
- PostgreSQL is the current source of truth.

The former JSONL operation format remains available only through the optional
test/development store; it is not the runtime persistence path.

## `extraction_runs`

Tracks one CLI execution:

- model name and local Ollama configuration
- extraction and prompt versions
- start, finish, status, and sanitized error
- scanned, relevant, skipped, processed, fact, and failure counts

## `message_processing_state`

Uses `(message_id, extraction_version)` as its primary key. It records:

- processing status
- relevance decision and deterministic reasons
- extraction run and attempt count
- validated raw local-model output
- sanitized failure details and processing timestamps

This key prevents duplicate extraction for the same version while allowing a
new version to process the same raw message non-destructively.

## `extracted_facts`

Each row is one fact attributed to one raw message:

- fact type
- event, task, owner, deadline, status, and value fields
- confidence and explicit/inferred evidence classification
- source message, extraction run, extraction version, and ordinal
- active flag reserved for later invalidation workflows

The unique key `(source_message_id, extraction_version, ordinal)` prevents
duplicates. Extracted rows remain historical evidence when Phase 4 derives
current state.

## Phase 4 organizational state

### `reconciliation_runs`

Tracks each incremental, retry, or rebuild execution and its applied, deferred,
unchanged, and failed counts.

### `events` and `event_aliases`

Events have deterministic internal IDs, guild scope, canonical names, and
normalized names. Aliases are unique within a guild and retain their source fact
when available.

### `tasks`

Tasks have deterministic internal IDs, guild scope, an optional event link, and
canonical and normalized titles. Mutable task data is stored separately.

### `current_state_values`

Stores one current JSON value per `(entity_type, entity_id, field)`. Each value
records its source fact, source message, confidence, evidence kind, and effective
time. Fields cover status, owner, deadlines, location, funding, sponsorship,
blockers, decisions, logistics, and other operational domains.

### `state_changes`

The append-only audit trail records previous and new values, change
classification, policy reason, reconciliation confidence, source fact, source
message, and effective time. A fact/entity/field uniqueness constraint prevents
duplicate transitions.

### `fact_reconciliation_state`

Tracks each fact as processing, applied, unchanged, unresolved, or failed. It
stores the resolved entity, outcome, reason, attempt count, and run reference.

### `unresolved_facts`

Preserves facts that cannot be mapped or classified safely. It records retry
metadata, candidate details, and any validated local-model proposal. Resolution
marks the row resolved instead of erasing its history.

All Phase 4 tables are derived from active facts. `rebuild` replaces only this
derived projection and preserves raw messages and extracted facts.

## Phase 5 event playbooks

### `playbooks`

Stores immutable playbook identities by key and version, event type, overlay
flag, active status, and a SHA-256 definition hash. Changing a synchronized
version is rejected; edits require a new version.

### `playbook_requirements`

Stores requirement metadata, including required/optional status, criticality,
owner, lead times, completion criteria, expected evidence, failure modes,
sponsor dependency, next-step template, and deterministic evaluation config.

### `requirement_dependencies`

Links requirements to prerequisites in the same resolved playbook definition.

### `event_playbooks`

Records the base playbook and overlays detected for an event, including the
reason and confidence. Assignments are replaced on each evaluation.

### `event_requirement_state`

Stores the current status, urgency, confidence, evidence, recommendation, and
rationale for each event/requirement pair. Evidence retains fact and source
message IDs where available.

### `requirement_evaluation_runs`

Stores each event-level readiness result and status counts. Readiness is a
weighted percentage, not an unweighted count.

### `requirement_evaluations`

Append-only history for every requirement evaluated in a run, including
evidence and its readiness weight and earned points. Re-evaluation updates
current state while preserving prior snapshots.
