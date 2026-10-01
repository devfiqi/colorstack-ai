# Security

ColorStack AI processes private Discord content. Treat the bot token and local
message archive as sensitive organizational data.

## Secrets

- Store `DISCORD_TOKEN` only in the local `.env` file.
- Never commit tokens, credentials, `.env`, or copied terminal output containing
  secrets.
- Rotate a token immediately if it is pasted into chat, logs, or an issue.
- Keep `.env.example` limited to empty variable names.

## Local data

- Raw messages are stored in the local `colorstack_ai` PostgreSQL database.
- PostgreSQL listens on localhost and is not externally hosted.
- The retired JSONL archive in `data/`, if retained, remains Git-ignored.
- Do not attach the archive to issues, pull requests, or support requests.
- Use full-disk encryption and normal OS account protections on the host.
- Database dumps and backups must follow the same access restrictions.

## Discord access

- Grant the bot only the channels required for ingestion.
- Required channel permissions are `View Channel` and `Read Message History`.
- `Manage Threads` broadens private-thread discovery and should be granted only
  when needed.
- Keep privileged Message Content and Server Members intents enabled only while
  required by the ingestion design.
- Deny message and thread sending globally. If outbound messaging is added
  later, allow it only in `#it-dept` through a channel-specific override.
- Follow the full [bot communication policy](BOT_PERMISSIONS.md).

## Local model

- `OLLAMA_BASE_URL` must resolve to localhost.
- Discord context is sent only to the configured local Ollama process.
- Do not configure a remotely hosted or tunneled Ollama endpoint.
- Raw prompts and model responses may contain private content; keep extraction
  tables and database backups local.

## Dependency and code changes

- Review dependency updates before merging.
- Keep extraction local. Reasoning may use the explicitly approved provider
  only with bounded Phase 6 context; never send the full archive or unrelated
  conversations.
- Keep the dashboard API bound to loopback unless authentication,
  authorization, and deployment controls are added first.
- Any hosted or non-loopback API/dashboard deployment must add authentication,
  authorization, audit logging, and data-retention controls first.

## Reporting a security issue

Do not open a public issue containing credentials or Discord content. Contact
the repository owner privately, rotate exposed credentials, and preserve only
the minimum diagnostic information needed.
