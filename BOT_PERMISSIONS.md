# Bot communication policy

The ColorStack AI bot is read-only everywhere except `#it-dept`.

## Allowed

- Read accessible Discord channels and threads for ingestion.
- Send messages directly in `#it-dept` only.

## Denied

- Sending messages in any other channel.
- Sending messages in threads, including threads under `#it-dept`.
- Sending direct messages.
- Replying, reacting, creating threads, or posting attachments outside the
  explicitly allowed channel.
- Falling back to another channel when `#it-dept` is missing or inaccessible.

## Server-side enforcement

Configure the bot role in Discord with:

1. Deny `Send Messages`, `Send Messages in Threads`, `Create Public Threads`,
   and `Create Private Threads` at the server role level.
2. In the `#it-dept` channel permission override, allow `Send Messages` only.
3. Keep thread-sending and thread-creation permissions denied.
4. Keep `View Channel` and `Read Message History` wherever ingestion is needed.

Discord permission overrides are the authoritative control. Documentation or
application checks must not be treated as a replacement for server permissions.

## Application enforcement

Any future outbound-message feature must:

- Use an explicit `DISCORD_ALLOWED_SEND_CHANNEL_ID` value for `#it-dept`.
- Compare the destination channel ID before every outbound action.
- Fail closed when the variable is missing, invalid, or does not match.
- Never use a channel name as the security boundary.
- Reject DMs and thread destinations.

The current application has no outbound messaging feature.
