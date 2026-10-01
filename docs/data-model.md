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
duplicates. Phase 3 does not reconcile competing facts or update organizational
current state.
