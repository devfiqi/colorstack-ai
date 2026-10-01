# Data model

Phase 1 writes newline-delimited JSON to
`data/discord-messages.jsonl`. Each line is an immutable operation record.
Field names use camel case in serialized output.

## Upsert operation

```json
{
  "operation": "upsert",
  "recordedAt": "2026-09-30T23:28:56.135000+00:00",
  "message": {
    "id": "123",
    "guildId": "456",
    "channelId": "789",
    "channelName": "events",
    "threadId": null,
    "authorId": "321",
    "username": "member",
    "displayName": "Member",
    "content": "Message text",
    "createdAt": "2026-09-30T22:00:00Z",
    "editedAt": null,
    "replyToMessageId": null,
    "attachments": [],
    "reactions": []
  }
}
```

Message fields:

- `id`: Discord message snowflake; the historical deduplication key.
- `guildId`: Discord guild snowflake, or `null` outside a guild.
- `channelId` and `channelName`: source channel identity.
- `threadId`: source thread ID when the channel is a thread.
- `authorId`, `username`, and `displayName`: author identity snapshot.
- `content`: message text available through the Message Content intent.
- `createdAt` and `editedAt`: Discord timestamps.
- `replyToMessageId`: referenced message ID when the message is a reply.
- `attachments`: attachment ID, name, URL, content type, and byte size.
- `reactions`: emoji representation and observed count.

## Delete operation

```json
{
  "operation": "delete",
  "recordedAt": "2026-09-30T23:30:00+00:00",
  "deletion": {
    "id": "123",
    "guildId": "456",
    "channelId": "789",
    "deletedAt": "2026-09-30T23:30:00+00:00"
  }
}
```

## Semantics

- Initial history uses insert-if-absent behavior based on message ID.
- Live creates and edits append upsert snapshots.
- Deletes append tombstones and do not erase earlier snapshots.
- On startup, the local store scans prior upserts to rebuild its known-ID set.
- Consumers must apply operations in file order to derive the latest state.
- `recordedAt` is ingestion time; message timestamps come from Discord.
