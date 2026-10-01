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

## Dependency and code changes

- Review dependency updates before merging.
- Keep extraction and reasoning local unless leadership explicitly approves an
  external processor and its data-handling terms.
- Any future API or dashboard must add authentication, authorization, audit
  logging, and data-retention controls before deployment.

## Reporting a security issue

Do not open a public issue containing credentials or Discord content. Contact
the repository owner privately, rotate exposed credentials, and preserve only
the minimum diagnostic information needed.
