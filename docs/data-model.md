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
